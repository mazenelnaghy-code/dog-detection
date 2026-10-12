"""Export a YOLO model for fast inference on the Raspberry Pi.

    python training/export.py --weights yolo11n.pt --format ncnn --imgsz 640 --out models
    python training/export.py --weights models/dog_yolo11n.pt --format ncnn --imgsz 640

NCNN is the fastest format on Raspberry Pi CPUs. Use the same --imgsz as model.imgsz in
config/pi.yaml. 640 finds the most dogs (~8-10 FPS on a Pi 5); 416 is ~2x faster (Pi 4)
but misses more small / far dogs; 320 misses too many.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--weights", default="yolo11n.pt")
    p.add_argument("--format", default="ncnn", choices=["ncnn", "onnx", "openvino", "tflite"])
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--out", type=Path, default=Path("models"))
    a = p.parse_args(argv)

    from ultralytics import YOLO

    exported = Path(YOLO(a.weights).export(format=a.format, imgsz=a.imgsz))
    a.out.mkdir(parents=True, exist_ok=True)
    target = a.out / exported.name
    if exported.resolve() != target.resolve():
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        shutil.move(str(exported), target)
    print(f"\nExported: {target}\nIn your config set:\nmodel:\n  path: {target.as_posix()}\n"
          f"  imgsz: {a.imgsz}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
