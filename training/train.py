"""Fine-tune YOLO11n on the dog dataset (starts from COCO weights = transfer learning).

    python training/train.py --data datasets/dogs/data.yaml --epochs 60 --device 0   # GPU
    python training/train.py --data datasets/dogs/data.yaml --epochs 3 --device cpu  # slow test

No GPU? Use notebooks/train_colab.ipynb on Google Colab (free GPU).
The best weights are copied to models/dog_yolo11n.pt.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data", default="datasets/dogs/data.yaml")
    p.add_argument("--model", default="yolo11n.pt", help="starting weights (yolov8n.pt also works)")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default=None, help="0 for the first GPU, or cpu")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--patience", type=int, default=15, help="stop early after N epochs w/o gain")
    p.add_argument("--fraction", type=float, default=1.0, help="use part of the data (tests)")
    p.add_argument("--name", default="dog_yolo11n")
    p.add_argument("--out", type=Path, default=Path("models"))
    a = p.parse_args(argv)

    from ultralytics import YOLO

    model = YOLO(a.model)
    model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device,
                workers=a.workers, patience=a.patience, fraction=a.fraction,
                project=str(Path("runs").resolve()),
                name=a.name, exist_ok=True, plots=True)
    best = Path(model.trainer.best)
    metrics = YOLO(best).val(data=a.data, imgsz=a.imgsz, device=a.device, plots=False)
    a.out.mkdir(parents=True, exist_ok=True)
    final = a.out / f"{a.name}.pt"
    shutil.copy2(best, final)
    print(f"\nmAP50 = {metrics.box.map50:.3f}   mAP50-95 = {metrics.box.map:.3f}")
    print(f"Saved {final}\nNext: python training/export.py --weights {final} --format ncnn "
          f"--imgsz 640 --out {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
