# Training the dog detector

The system works out of the box with the **COCO-pretrained YOLO11n** (`yolo11n.pt`; the original
team used YOLOv8n, which works too). COCO class 16 is "dog", and the detector also counts the
look-alike labels COCO gives Egyptian street dogs (see [docs/EVALUATION.md](../docs/EVALUATION.md)). Fine-tuning is an *optional* upgrade that makes
the model a dog specialist for your camera and your location:

* **one class only (dog)**: no capacity spent on 79 other classes;
* **hard negatives**: images of people and cats with no dog, so children and cats do not
  trigger the repeller;
* **your own photos**: street dogs around your school, at your camera height and lighting
  (including night shots from a NoIR camera), which matter more than anything else.

## 1. Build the dataset

```bash
python training/prepare_coco_dogs.py --out datasets/dogs            # ~4,500 dog images + negatives
python training/prepare_coco_dogs.py --out datasets/dogs --max-dogs 1500   # faster
```

Only the needed COCO images are downloaded (individually), not the full 19 GB dataset.
Images are stored under `datasets/`, which is git-ignored. COCO images keep their original
Flickr licences, so do not re-upload them to GitHub.

### Adding your own photos (recommended)

1. Take photos/videos of dogs where the system will be installed (different times of day).
2. Label them with [Roboflow](https://roboflow.com), [CVAT](https://www.cvat.ai) or
   [Label Studio](https://labelstud.io): one class named `dog`. Also add some photos with
   **no dog** (kids playing, empty yard) and leave them unlabelled.
3. Export in **YOLOv8 / YOLO** format and merge:

```bash
python training/prepare_coco_dogs.py --out datasets/dogs --extra path/to/my_dogs
```

Both layouts are supported: `images/train` + `labels/train` and Roboflow's `train/images` +
`train/labels` (`valid` is treated as `val`).

## 2. Train

No GPU? Open [`notebooks/train_colab.ipynb`](../notebooks/train_colab.ipynb) in Google Colab (free T4 GPU).

```bash
python training/train.py --data datasets/dogs/data.yaml --epochs 60 --device 0
```

Training curves, confusion matrix and sample predictions are saved in `runs/dog_yolo11n/`.
The best weights are copied to `models/dog_yolo11n.pt`, and the script prints mAP50 / mAP50-95.

## 3. Export for the Raspberry Pi

```bash
python training/export.py --weights models/dog_yolo11n.pt --format ncnn --imgsz 640 --out models
```

Then set `model.path: models/dog_yolo11n_ncnn_model` and `model.imgsz: 640` in your Pi config.
A fine-tuned model has a single class (dog), so `model.also_count` is ignored automatically.

## 4. Check that it really got better

Always compare against the stock model **on photos from your own site** that were not used
for training:

```bash
python tools/evaluate.py --dogs my_site/dogs --no-dogs my_site/no_dogs     --model yolo11n.pt models/dog_yolo11n.pt --imgsz 640 --variant none night
```

Keep the fine-tuned model only if it finds more dogs without more false alarms.
