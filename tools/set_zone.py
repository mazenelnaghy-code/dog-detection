"""Draw the danger zone with the mouse instead of guessing numbers.

    python tools/set_zone.py --config config/local.yaml              # live camera (on the Pi desktop)
    python tools/set_zone.py --source samples/dogs/street_dog_0068.jpg
    python tools/set_zone.py --config config/local.yaml --write      # save into the config file

Drag a rectangle over the area where a dog is "too close" (usually the lower part of the image,
in front of the gate or playground), then press ENTER or SPACE. Press C to cancel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def roi_to_rect(roi: tuple[int, int, int, int], width: int, height: int) -> list[float]:
    """OpenCV ROI (x, y, w, h) in pixels -> zone.rect [x1, y1, x2, y2] as fractions."""
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        raise ValueError("empty selection")
    return [round(x / width, 3), round(y / height, 3),
            round(min(x + w, width) / width, 3), round(min(y + h, height) / height, 3)]


def write_rect(config_path: Path, rect: list[float]) -> None:
    """Set zone.rect in a YAML config, keeping its other settings (comments are not kept)."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    data = data or {}
    data.setdefault("zone", {})["rect"] = rect
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import cv2

    from dog_repeller.app import build_parser, config_from_args
    from dog_repeller.sources import open_source

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--config", type=Path, help="config to read the camera from (and --write to)")
    p.add_argument("--source", help="camera / video / photo to draw on")
    p.add_argument("--write", action="store_true", help="save zone.rect into --config")
    a = p.parse_args(argv)
    if a.write and not a.config:
        p.error("--write needs --config")

    app_args = ["--sim"] + (["--config", str(a.config)] if a.config else [])
    app_args += ["--source", a.source] if a.source else []
    cfg = config_from_args(build_parser().parse_args(app_args))
    src = open_source(cfg.camera)
    frame = None
    for _ in range(10):  # let a live camera settle its exposure
        frame = src.read() if frame is None or src.is_live else frame
    src.close()
    if frame is None:
        print("No image from the source", file=sys.stderr)
        return 1

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = cfg.zone.rect
    cv2.rectangle(frame, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), (0, 210, 255), 1)
    title = "Drag the danger zone, then ENTER (current zone in yellow)"
    roi = cv2.selectROI(title, frame, showCrosshair=False)
    cv2.destroyAllWindows()
    try:
        rect = roi_to_rect(tuple(int(v) for v in roi), w, h)
    except ValueError:
        print("Cancelled - nothing changed.")
        return 1
    print(f"\nzone:\n  rect: {rect}")
    if a.write:
        write_rect(a.config, rect)
        print(f"Saved to {a.config}. Restart the service: sudo systemctl restart dog-repeller")
    return 0


if __name__ == "__main__":
    sys.exit(main())
