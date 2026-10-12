# Evaluation on Egyptian street dogs

The system is meant for Egypt, so it was tested on **Egyptian street dogs** (baladi dogs), not
only on the COCO pet photos the model was trained on. The tests below exposed a real weakness of
the stock model and led to the defaults the project now uses.

## Test set

Freely licensed photos from Wikimedia Commons, downloaded with `tools/fetch_commons.py`. Every
image was checked by eye before use.

| Folder | Images | Source category | Removed after review |
|---|---|---|---|
| `dogs/` | **236** | Dogs of Egypt (Luxor, Aswan, Cairo, …), Feral dogs in Egypt | 7 (2 drawings, 1 unclear, 2 with no visible dog, 2 with dogs only a few pixels tall) |
| `no_dogs/` (cats) | **114** | Feral cats in Egypt, Cats of Egypt | 1 (it also contained dogs) |
| `kids/` | **113** | Children of Egypt | 3 (drawings/paintings) |

The dog photos show real street conditions: dogs lying in the dust, curled up, in groups,
behind cages and railings, puppies, fog, dark and light coats. The child photos include kids
running, crouching, hanging from trees, a girl beside a donkey, and calves on a farm.

**Metric.** For each image, does the system report at least one dog? "Dogs found" is the share
of dog images with a detection. "False alarms" is the share of cat or child images with one.
Confidence threshold 0.25. Times were measured on an Intel i7-8550U laptop CPU.

## 1. The stock models miss many Egyptian dogs

Counting only the COCO class "dog", as the original prototype did:

| Model | 416 px: dogs found | 416 px: cat false alarms | 640 px: dogs found | 640 px: cat false alarms |
|---|---|---|---|---|
| YOLOv8n (original prototype) | 62 % | 11 % | 69 % | 12 % |
| YOLO11n | 63 % | 10 % | 74 % | 7 % |
| YOLO26n | 65 % | 16 % | 73 % | 11 % |

## 2. Why: baladi dogs are seen, but called something else

Of the 61 Egyptian dogs YOLO11n missed at 640 px, almost all were detected but labelled as a
different animal: about 20 **cow**, 15 **bear**, 8 **sheep**, 6 **horse**, plus elephant and zebra.
Only 3 were not detected at all. COCO's dog photos are mostly pets, so a dusty tan street dog
looks to the model like livestock or a bear cub.

**Fix (`model.also_count`):** count these look-alike classes as "dog". **Cat and person can
never be added**, so children never count. Each class contributes differently (YOLO11n, 640 px):

| Also count | Dogs found gained | Cat false alarms added |
|---|---|---|
| cow | +9.7 % | 0 % |
| bear | +7.6 % | **+7.9 %** (dark cats look like bear cubs) |
| sheep | +4.7 % | +1.8 % |
| horse | +3.4 % | 0 % |
| elephant / zebra | +1.2 % | 0 % |

`model.compete` puts every class through one shared overlap check (class-agnostic NMS), so a
box that is clearly a cat or a person removes a weaker "dog" box on the same spot.

## 3. Result with the shipped defaults

The defaults are YOLO11n, `compete: true` and `also_count` including bear:

| Model | Size | Dogs found | Child false alarms | Cat false alarms | ms / frame (laptop) |
|---|---|---|---|---|---|
| **YOLO11n (PyTorch, PC default)** | 640 | **97 %** (228/236) | **4 %** (5/113) | 15 % | 94 |
| **YOLO11n NCNN (Pi default)** | 640 | **96 %** (227/236) | **4 %** (4/113) | 17 % | 123 |
| YOLO11n | 416 | 92 % | 4 % | 19 % | 58 |
| YOLOv8n (original) | 640 | 94 % | 5 % | 18 % | 84 |
| YOLO26n | 640 | 95 % | – | 16 % | 112 |

What the child false alarms were (YOLO11n, 640 px):

- **2 real animals:** a donkey next to a girl, and calves on a farm. The repeller would fire,
  which is harmless.
- **3 mistakes:** a black-and-white photo of a boy hanging upside down from a tree, a blurry
  child behind a car window, and an old hand-coloured photograph.

The live system adds two more filters on top of these per-photo numbers: the danger zone or
distance rule, and confirmation in 3 of 6 frames.

**Cats vs. dogs trade-off:** with "bear" counted, about 15 % of cat photos trigger. A burst of
ultrasound does not harm a cat (commercial repellers target cats too), while a missed dog near
children is the failure that matters. If cats trigger it too often at your site, remove `bear`:
dogs found drops to 89 % and cat false alarms to 7 %.

## 4. Harder camera conditions (YOLO11n, final settings, dogs vs. children)

| Condition (simulated) | 640 px | 416 px |
|---|---|---|
| Normal | 97 % | 92 % |
| Night: NoIR camera, grayscale, dark, noisy | 81 % | 73 % |
| Far away: image shrunk to 40 % | 81 % | 69 % |
| Strong motion blur: running dog | 62 % | 72 % |

Child false alarms stayed between 1 % and 5 % in every condition.

**Motion blur** is the weakest case. On the Pi, `camera.fps` is passed to the camera as its
frame rate, which also caps the exposure time and so reduces blur. A dog is seen in many
frames while it approaches, and only 3 of 6 need to agree.

## 5. Speed on the Raspberry Pi (not measured here)

No Pi was available while writing this. The official Ultralytics Raspberry Pi guide reports
**67 ms** NCNN inference for YOLO26n at 640 px on a Pi 5, and YOLO11n about 15 % slower. The
expected speed is therefore **about 8–10 FPS on a Pi 5** at 640 px. A Pi 4 is roughly 2–3×
slower; use 416 px there. Measure your own Pi with:

```bash
python tools/evaluate.py --dogs my_test/dogs --no-dogs my_test/no_dogs --model models/yolo11n_ncnn_model --imgsz 640
```

## Limitations, read before trusting the numbers

- These are **single photos taken by people**, mostly at eye level. A camera on a pole or
  tripod sees dogs from a different angle and distance.
- Many dog photos come from a few photographers (for example a long series of one dog family in
  Luxor), so results are correlated and the real uncertainty is larger than the sample size
  suggests.
- Night, distance and blur are **simulated**. A real NoIR camera with IR light looks different.
- **The best test is your own site.** Record a few days of video at the installation point,
  sort frames into `dogs/` and `no_dogs/`, and run `tools/evaluate.py`. If results are weak,
  label those frames and fine-tune (see `training/README.md`). Your own footage beats any public
  dataset.

## Reproduce

```bash
python tools/fetch_commons.py datasets/egypt_eval/raw_dogs 250 2 "Category:Dogs of Egypt" "Category:Feral dogs in Egypt"
python tools/fetch_commons.py datasets/egypt_eval/raw_cats 120 1 "Category:Feral cats in Egypt" "Category:Cats of Egypt"
python tools/fetch_commons.py datasets/egypt_eval/raw_kids 120 0 "Category:Children of Egypt"
# review the images, sort them into dogs/ no_dogs/ kids/ folders, then:
python tools/evaluate.py --dogs datasets/egypt_eval/dogs --no-dogs datasets/egypt_eval/kids \
    --model yolo11n.pt yolov8n.pt --imgsz 416 640 --variant none night far blur
```

Wikimedia categories change over time, so a new download will not be byte-identical.
