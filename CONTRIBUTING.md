# Contributing

Thanks for helping keep children safe from stray dogs. Issues and pull requests are welcome,
in **English or Arabic**.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt && pip install --no-deps -e .
python -m pytest            # tests: no camera, GPU or Raspberry Pi needed
ruff check .                # lint
python -m dog_repeller --demo
```

## Rules of the road

- **Safety first.** Changes to `controller.py`, `hardware.py` or the relay logic need a test
  showing the repeller still ends up OFF (on errors, exit, disarm, watchdog).
- **Keep the core light.** Never import `ultralytics`, `picamera2` or `gpiozero` at module top
  level; import them inside the function that needs them, so CI and tests stay fast.
- **Detection changes need numbers.** If you change model, thresholds or `also_count`, run
  `tools/evaluate.py` on dogs and on children/cats, and put before/after results in the PR.
- **Privacy.** Never commit photos where children can be identified, recordings, or your
  `config/local.yaml` (it holds the dashboard password).
- One topic per pull request, with a clear description of *why*.

## Useful tools

| Tool | Purpose |
|---|---|
| `tools/evaluate.py` | dogs found / false alarms / speed on your own image folders |
| `tools/hardware_check.py` | self-test of a built device (camera, model, buzzer, relay, power) |
| `tools/set_zone.py` | draw the danger zone with the mouse and save it to the config |
| `tools/calibrate_focal.py` | focal length for distance estimation |
| `tools/fetch_commons.py` | download a freely-licensed test set from Wikimedia Commons |
| `tools/make_gif.py` | turn a `--record` video into a GIF for docs |
