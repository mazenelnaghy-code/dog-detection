# Changelog

## 1.1.0 — 2026-10-08: tested on Egyptian street dogs

- **Detection tuned for baladi dogs.** On 236 Egyptian street-dog photos the stock model
  labelled many dogs as cow, bear, sheep or horse. These labels now count as dogs (never cat or
  person), and all classes compete in one shared NMS. Dogs found went from 72 % to 97 %, with
  4 % false alarms on 113 photos of Egyptian children. Report in `docs/EVALUATION.md`.
- Default model is now **YOLO11n** at 640 px on PC and Pi (NCNN). YOLOv8n still works.
- **One-command demo:** `python -m dog_repeller --demo`, using bundled public-domain samples.
  Also available as a Colab notebook, a Codespaces config and a Dockerfile.
- **Safety:** watchdog thread forces the repeller OFF if the program freezes; systemd now
  restarts the service after a camera failure (it used to exit with code 0 and stay off); the
  camera tolerates 10 s hiccups; a failed dashboard no longer stops protection.
- `camera.realtime` plays video files like a live camera; `--record` saves annotated video.
- New tools: `evaluate.py`, `hardware_check.py`, `set_zone.py`, `fetch_commons.py`, `make_gif.py`;
  step-by-step field testing guide in `docs/TESTING.md`.
- Pi camera honours `camera.fps`, which caps exposure and reduces motion blur.
- `setup_pi.sh` fixes: works when `$USER` is unset, refuses to run under `sudo`, exports YOLO11n.
- gpiozero mock-pin tests, ruff lint in CI, contributing guide, issue templates.

## 1.0.0 — 2026-10-08: first release

- Rebuild of the graduation project "AI-Powered Dog Detection and Repellent System"
  (Faculty of Engineering, East Port Said National University): YOLOv8n detection, danger zone
  with centre dot, focal-length distance, buzzer, relay-driven ultrasonic repeller, web
  dashboard, Raspberry Pi setup script, training pipeline, English and Arabic docs.
