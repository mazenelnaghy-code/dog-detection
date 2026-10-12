"""Measure how well a model detects dogs on YOUR images - and how fast it runs on this machine.

Put photos in two folders - no labelling needed:
    my_test/dogs/      every image contains at least one dog
    my_test/no_dogs/   no dog at all (children, cats, empty street, cars ...)

    python tools/evaluate.py --dogs my_test/dogs --no-dogs my_test/no_dogs
    python tools/evaluate.py --dogs d --no-dogs n --model yolov8n.pt yolo11n.pt --imgsz 416 640
    python tools/evaluate.py --dogs d --no-dogs n --variant night far blur --save-failures out/

Variants simulate harder camera conditions on the same photos:
    night  NoIR camera at night (grayscale, dark, sensor noise)
    far    dogs further away (image shrunk to 40 % on a grey background)
    blur   a running dog (motion blur)

Run it on the Raspberry Pi to get real frames-per-second numbers for your hardware.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VARIANTS = ("none", "night", "far", "blur")


# ---- camera-condition simulation (pure, unit-tested) -------------------------------------
def simulate(img: np.ndarray, variant: str, seed: int = 0) -> np.ndarray:
    if variant == "none":
        return img
    if variant == "night":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        dark = np.power(gray, 1.8) * 0.6  # darker, lower contrast
        noise = np.random.default_rng(seed).normal(0, 0.04, dark.shape)
        out = np.clip((dark + noise) * 255, 0, 255).astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    if variant == "far":
        h, w = img.shape[:2]
        small = cv2.resize(img, (max(1, int(w * 0.4)), max(1, int(h * 0.4))),
                           interpolation=cv2.INTER_AREA)
        canvas = np.full_like(img, 114)
        y, x = (h - small.shape[0]) // 2, (w - small.shape[1]) // 2
        canvas[y:y + small.shape[0], x:x + small.shape[1]] = small
        return canvas
    if variant == "blur":
        k = max(3, img.shape[1] // 60) | 1
        kernel = np.zeros((k, k), np.float32)
        kernel[k // 2, :] = 1.0 / k
        return cv2.filter2D(img, -1, kernel)
    raise ValueError(f"unknown variant {variant!r}; choose from {VARIANTS}")


# ---- scoring (pure, unit-tested) ----------------------------------------------------------
@dataclass
class Score:
    dogs_found: int = 0
    dogs_total: int = 0
    false_alarms: int = 0
    no_dog_total: int = 0
    seconds: float = 0.0
    frames: int = 0
    missed: list[str] = field(default_factory=list)
    alarms: list[str] = field(default_factory=list)

    def add(self, name: str, has_dog: bool, detected: bool, seconds: float) -> None:
        self.frames += 1
        self.seconds += seconds
        if has_dog:
            self.dogs_total += 1
            self.dogs_found += detected
            if not detected:
                self.missed.append(name)
        else:
            self.no_dog_total += 1
            self.false_alarms += detected
            if detected:
                self.alarms.append(name)

    @property
    def recall(self) -> float:
        return self.dogs_found / self.dogs_total if self.dogs_total else 0.0

    @property
    def false_alarm_rate(self) -> float:
        return self.false_alarms / self.no_dog_total if self.no_dog_total else 0.0

    @property
    def ms_per_frame(self) -> float:
        return 1000 * self.seconds / self.frames if self.frames else 0.0


def list_images(folder: Path | None) -> list[Path]:
    if folder is None:
        return []
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def run(detector, dogs: list[Path], no_dogs: list[Path], variant: str,
        save_dir: Path | None = None) -> Score:
    score = Score()
    for path, has_dog in [(p, True) for p in dogs] + [(p, False) for p in no_dogs]:
        img = cv2.imread(str(path))
        if img is None:
            continue
        img = simulate(img, variant)
        t0 = time.perf_counter()
        dets = detector.detect(img)
        score.add(path.name, has_dog, bool(dets), time.perf_counter() - t0)
        if save_dir and (bool(dets) != has_dog):
            sub = save_dir / ("missed_dogs" if has_dog else "false_alarms")
            sub.mkdir(parents=True, exist_ok=True)
            for d in dets:
                x1, y1, x2, y2 = (int(v) for v in d.box)
                cv2.rectangle(img, (x1, y1), (x2, y2), (40, 40, 230), 2)
                cv2.putText(img, f"dog {d.conf:.2f}", (x1, max(15, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 230), 2)
            cv2.imwrite(str(sub / f"{variant}_{path.stem}.jpg"), img)
    return score


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dogs", type=Path, help="folder of images that contain dogs")
    p.add_argument("--no-dogs", type=Path, help="folder of images without dogs")
    p.add_argument("--model", nargs="+", default=["yolo11n.pt"])
    p.add_argument("--imgsz", type=int, nargs="+", default=[640])
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--no-compete", action="store_true", help="score the dog class only")
    p.add_argument("--dog-only", action="store_true", help="do not count dog look-alike classes")
    p.add_argument("--variant", nargs="+", default=["none"], choices=VARIANTS)
    p.add_argument("--save-failures", type=Path, help="save missed dogs / false alarms here")
    p.add_argument("--csv", type=Path, help="append results to this CSV file")
    a = p.parse_args(argv)
    if not a.dogs and not a.no_dogs:
        p.error("give --dogs and/or --no-dogs")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from dog_repeller.config import ModelConfig
    from dog_repeller.detector import DogDetector

    dogs, no_dogs = list_images(a.dogs), list_images(a.no_dogs)
    print(f"{len(dogs)} dog images, {len(no_dogs)} no-dog images\n")
    header = f"{'model':<34}{'imgsz':>6}{'variant':>8}{'dogs found':>14}{'false alarms':>15}{'ms/frame':>10}"
    print(header + "\n" + "-" * len(header))
    rows = []
    for model in a.model:
        for imgsz in a.imgsz:
            extra = {"also_count": []} if a.dog_only else {}
            detector = DogDetector(ModelConfig(path=model, imgsz=imgsz, conf=a.conf,
                                               compete=not a.no_compete, **extra))
            for variant in a.variant:
                save = a.save_failures / f"{Path(model).stem}_{imgsz}" if a.save_failures else None
                s = run(detector, dogs, no_dogs, variant, save)
                print(f"{model:<34}{imgsz:>6}{variant:>8}"
                      f"{f'{s.dogs_found}/{s.dogs_total} ({s.recall:.0%})':>14}"
                      f"{f'{s.false_alarms}/{s.no_dog_total} ({s.false_alarm_rate:.0%})':>15}"
                      f"{s.ms_per_frame:>10.0f}")
                rows.append({"model": model, "imgsz": imgsz, "conf": a.conf, "variant": variant,
                             "dogs_found": s.dogs_found, "dogs_total": s.dogs_total,
                             "false_alarms": s.false_alarms, "no_dog_total": s.no_dog_total,
                             "ms_per_frame": round(s.ms_per_frame, 1)})
    if a.csv:
        new = not a.csv.exists()
        with open(a.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            if new:
                w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
