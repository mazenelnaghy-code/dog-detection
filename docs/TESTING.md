# Testing guide: from the desk to the kindergarten gate

([العربية](TESTING.ar.md)) Work through these stages in order. Each one catches problems the previous one cannot. Nothing
here needs programming knowledge.

## Stage 0: no hardware (any PC, 5 minutes)

| Test | Command | Expected |
|---|---|---|
| Demo | `python -m dog_repeller --demo` | children and cat: nothing; dog: beep, repeller bursts, back to idle |
| Your photos | `python tools/evaluate.py --dogs samples/dogs --no-dogs samples/no_dogs` | most dogs found, no false alarms |
| Your videos | `python -m dog_repeller --sim --source my.mp4 --set camera.realtime=true` | boxes on dogs, sensible log |
| Software tests | `python -m pytest` | all pass |

No install at all: use the Colab notebook (`notebooks/demo_colab.ipynb`) and upload a photo.

## Stage 1: bench test of the built device (30 minutes)

Do this on a table, **before** connecting the 12 V repeller.

1. Run `bash deploy/setup_pi.sh` as your normal user (not sudo).
2. Run `.venv/bin/python tools/hardware_check.py --config config/local.yaml`.
   - **Pi health** must not show `POWER PROBLEM`. That means a weak supply; use the official
     5 V 5 A (Pi 5) or 5 V 3 A (Pi 4) adapter.
   - **Camera** must PASS. Open `hardware_check.jpg` and check the image is the right way up
     (if not, set `camera.rotate: 180`).
   - **Model** shows the real FPS. Below about 3 FPS (e.g. on a Pi 4), switch to 416 px:
     `.venv/bin/python training/export.py --weights yolo11n.pt --format ncnn --imgsz 416 --out models`
     and set `model.imgsz: 416` in `config/local.yaml`.
   - **Buzzer**: you hear it. **Repeller relay**: you hear it click and its LED lights.
3. Measure with a multimeter: relay COM–NO is open (∞ Ω) when idle and closed during the test.
4. Pull the power plug while the relay is ON. When the Pi boots again the relay must stay
   **OFF**. If it clicks on during boot, see the README troubleshooting table.

## Stage 2: watch only, on site (1–3 days)

Mount the camera where it will stay. Run **without** the repeller connected, or set
`hardware.backend: sim`, so nothing fires while you tune.

1. Draw the danger zone on the real view: `python tools/set_zone.py --config config/local.yaml --write`.
2. Optional, for the distance rule: stand 3 m from the camera and run
   `python tools/calibrate_focal.py measure --image photo.jpg --distance 3 --real-height <your height in m>`.
3. Record what happens: `python -m dog_repeller --config config/local.yaml --sim --record day1.mp4`.
   Recording shows children; keep the file private and delete it after review.
4. Review the recording and the log (`journalctl -u dog-repeller`):
   - **Missed dogs:** were they too far, or at night? Consider `model.imgsz: 640`, an IR light, or
     fine-tuning on these frames (see `training/README.md`).
   - **False alarms:** children, cats, shadows? Move or shrink the zone. If cats are the
     problem, remove `bear` from `model.also_count`.
5. Turn frames into a test set (`dogs/`, `no_dogs/`) and keep it. Re-run `tools/evaluate.py`
   after every change, so you know whether the change really helped.

## Stage 3: arm the repeller (with staff present)

1. Check the repeller frequency setting is **≥ 23 kHz**. Run `t` (test) from the dashboard
   with staff and a few children nearby, and confirm nobody hears it or is bothered.
2. Connect the repeller and set `hardware.backend: gpio`. Watch the first real dog encounters
   from a distance. Does the dog leave? Puppies and deaf or old dogs may not react.
3. Keep the default bursts (5 s on, 3 s off, rest after 6). Do not make it continuous: dogs
   get used to constant sound, and it is not kind.

## Stage 4: keep it working

| Every | Check |
|---|---|
| Day | dashboard reachable, status ARMED, FPS normal |
| Week | camera lens clean; `journalctl -u dog-repeller --since "1 week ago" \| grep -c "REPELLER ON"` looks plausible |
| Month | run `tools/hardware_check.py` again; check cables, fan and the 12 V adapter |
| After changes | `tools/evaluate.py` on your site test set, before vs. after |
