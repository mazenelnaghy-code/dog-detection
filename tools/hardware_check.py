"""Hardware self-check: run this FIRST after building the device (and whenever something is odd).

    python tools/hardware_check.py --config config/local.yaml          # on the Raspberry Pi
    python tools/hardware_check.py --sim --source samples/dogs --yes   # try it on any PC

Checks, in order:
  1. Pi health   - model, CPU temperature, under-voltage / throttling (weak power supply!)
  2. Camera      - frames arrive; saves a snapshot to hardware_check.jpg
  3. Model       - loads, finds a dog in a sample photo, measures real frames per second
  4. Buzzer      - beeps; asks you to confirm you heard it
  5. Repeller    - relay ON for 2 s; asks you to confirm the click / repeller LED

Exit code 0 = everything passed.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dog_repeller.app import build_parser, config_from_args  # noqa: E402
from dog_repeller.config import CameraConfig, ModelConfig  # noqa: E402
from dog_repeller.hardware import Buzzer, Repeller, create_outputs  # noqa: E402
from dog_repeller.sources import open_source  # noqa: E402

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
Result = tuple[str, str]


def check_system() -> Result:
    model_file = Path("/proc/device-tree/model")
    model = model_file.read_text(errors="ignore").strip("\x00\n") if model_file.exists() else ""
    info = [model or f"{platform.system()} {platform.machine()} (not a Raspberry Pi)",
            f"Python {platform.python_version()}"]
    status = PASS
    temp = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp.exists():
        celsius = int(temp.read_text()) / 1000
        info.append(f"CPU {celsius:.0f} °C")
        if celsius >= 80:
            status = WARN
            info.append("HOT - add a fan/heatsink")
    if shutil.which("vcgencmd"):
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout
        flags = int(out.strip().split("=")[-1], 16) if "=" in out else 0
        if flags & 0x50005:  # under-voltage / throttled now or since boot
            status = WARN
            info.append(f"POWER PROBLEM (throttled={hex(flags)}): use the official 5 V supply")
        else:
            info.append("power OK")
    return status, ", ".join(info)


def check_camera(cfg: CameraConfig, snapshot: Path, frames: int = 20) -> Result:
    try:
        src = open_source(cfg)
    except Exception as e:  # noqa: BLE001 - report any camera error to the user
        return FAIL, f"cannot open camera '{cfg.source}': {e}"
    got, last, t0 = 0, None, time.monotonic()
    try:
        while got < frames:
            frame = src.read()
            if frame is None:
                break
            got, last = got + 1, frame
    finally:
        src.close()
    if last is None:
        return FAIL, f"no frames from '{cfg.source}' (check the cable / rpicam-hello --list-cameras)"
    cv2.imwrite(str(snapshot), last)
    fps = got / max(time.monotonic() - t0, 1e-6)
    return PASS, f"{got} frames {last.shape[1]}x{last.shape[0]} at {fps:.0f} fps, snapshot: {snapshot}"


def check_model(cfg: ModelConfig, sample: Path, runs: int = 10) -> Result:
    from dog_repeller.detector import DogDetector

    try:
        detector = DogDetector(cfg)
    except Exception as e:  # noqa: BLE001
        return FAIL, f"cannot load {cfg.path}: {e}"
    img = cv2.imread(str(sample))
    if img is None:
        return WARN, f"model loaded, but sample photo {sample} is missing"
    found = detector.detect(img)
    t0 = time.perf_counter()
    for _ in range(runs):
        detector.detect(img)
    ms = 1000 * (time.perf_counter() - t0) / runs
    speed = f"{ms:.0f} ms/frame (~{1000 / ms:.1f} FPS)"
    if not found:
        return WARN, f"model loaded but saw no dog in {sample.name}; {speed}"
    status = PASS if ms < 500 else WARN
    hint = "" if status == PASS else " - slow: try model.imgsz 416"
    return status, f"dog found (conf {found[0].conf:.2f}); {speed}{hint}"


def check_outputs(buzzer: Buzzer, repeller: Repeller, ask: Callable[[str], bool | None]
                  ) -> list[tuple[str, Result]]:
    results = []
    buzzer.beep()
    time.sleep(1.0)
    heard = ask("Did you hear the buzzer beep?")
    results.append(("Buzzer", (PASS if heard else FAIL if heard is False else WARN,
                               "confirmed" if heard else "not heard" if heard is False
                               else "beeped (not confirmed)")))
    print("  Repeller ON for 2 s - keep children and pets away from the speaker.")
    repeller.set(True)
    time.sleep(2.0)
    repeller.set(False)
    clicked = ask("Did the relay click (and the repeller LED light up)?")
    results.append(("Repeller", (PASS if clicked else FAIL if clicked is False else WARN,
                                 "confirmed" if clicked else "no click" if clicked is False
                                 else "switched (not confirmed)")))
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--config", type=Path)
    p.add_argument("--source", help="override camera.source")
    p.add_argument("--sim", action="store_true", help="simulated buzzer/relay (PC)")
    p.add_argument("--yes", action="store_true", help="do not ask questions")
    p.add_argument("--snapshot", type=Path, default=Path("hardware_check.jpg"))
    a = p.parse_args(argv)
    app_args = ["--no-window", "--no-dashboard"] + (["--config", str(a.config)] if a.config else [])
    app_args += (["--source", a.source] if a.source else []) + (["--sim"] if a.sim else [])
    cfg = config_from_args(build_parser().parse_args(app_args))

    def ask(question: str) -> bool | None:
        if a.yes:
            return None
        return input(f"  {question} [y/n] ").strip().lower().startswith("y")

    results: list[tuple[str, Result]] = []
    for name, fn in (("Pi health", check_system),
                     ("Camera", lambda: check_camera(cfg.camera, a.snapshot)),
                     ("Model", lambda: check_model(cfg.model, ROOT / "samples/dogs/street_dog_0063.jpg"))):
        print(f"[{name}] checking ...", flush=True)
        results.append((name, fn()))
        print(f"  {results[-1][1][0]}: {results[-1][1][1]}")
    print(f"[Outputs] backend: {cfg.hardware.backend}")
    buzzer, repeller = create_outputs(cfg)
    try:
        results += check_outputs(buzzer, repeller, ask)
    finally:
        repeller.close()
        buzzer.close()

    print("\n" + "=" * 70)
    for name, (status, msg) in results:
        print(f"{status:<5} {name:<10} {msg}")
    print("=" * 70)
    failed = [n for n, (s, _) in results if s == FAIL]
    print("ALL GOOD" if not failed else f"FAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
