"""Build a YOLO "dog" dataset from COCO 2017 (+ optionally your own labelled photos).

* Positives: every COCO image that contains a dog; the dog boxes become class 0.
* Hard negatives: images with people / cats but no dog (empty label files). They teach the
  model NOT to fire on children or cats - important for a kindergarten.
* Only the selected images are downloaded (not the whole 19 GB COCO), using the YOLO-format
  COCO labels published by Ultralytics (~49 MB, downloaded once and cached).
* ``--extra`` merges your own datasets in YOLO format (e.g. a Roboflow "YOLOv8" export of street
  dogs photographed around your school). Their "dog" class is remapped to 0.

    python training/prepare_coco_dogs.py --out datasets/dogs
    python training/prepare_coco_dogs.py --out datasets/dogs --max-dogs 1500 --extra my_dogs/

Result: datasets/dogs/{images,labels}/{train,val} + datasets/dogs/data.yaml
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
import time
import urllib.request
import zipfile
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

LABELS_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco2017labels.zip"
IMAGE_URL = "http://images.cocodataset.org/{split}2017/{name}.jpg"
COCO_DOG, COCO_NEGATIVES = 16, {"person": 0, "cat": 15}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ---- pure helpers (unit-tested) ----------------------------------------------------------
def classes_in(lines: Iterable[str]) -> set[int]:
    return {int(float(line.split()[0])) for line in lines if line.strip()}


def convert_label_lines(lines: Iterable[str], keep: set[int], new_id: int = 0) -> list[str]:
    """Keep rows whose class is in ``keep`` (boxes: class cx cy w h) and renumber them."""
    out = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 5 and int(float(parts[0])) in keep:
            out.append(" ".join([str(new_id), *parts[1:5]]))
    return out


def select_images(labels: dict[str, list[str]], dog_class: int, negative_classes: set[int],
                  max_dogs: int | None, neg_ratio: float, seed: int) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    positives = sorted(n for n, ls in labels.items() if dog_class in classes_in(ls))
    candidates = sorted(n for n, ls in labels.items()
                        if dog_class not in (c := classes_in(ls)) and c & negative_classes)
    rng.shuffle(positives)
    rng.shuffle(candidates)
    positives = positives[:max_dogs] if max_dogs else positives
    negatives = candidates[:round(len(positives) * neg_ratio)]
    return positives, negatives


def write_data_yaml(out_dir: Path) -> Path:
    path = out_dir / "data.yaml"
    data = {"path": str(out_dir.resolve()), "train": "images/train", "val": "images/val",
            "names": {0: "dog"}}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def read_names(data_yaml: Path) -> list[str]:
    names = yaml.safe_load(data_yaml.read_text(encoding="utf-8")).get("names", [])
    return [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names)


def find_split_dirs(root: Path, split: str) -> list[tuple[Path, Path]]:
    """Support both ``images/train`` (Ultralytics) and ``train/images`` (Roboflow) layouts."""
    aliases = [split, "valid"] if split == "val" else [split]
    pairs = []
    for a in aliases:
        for img in (root / "images" / a, root / a / "images"):
            lbl = img.parent.parent / "labels" / a if img.parent.name == "images" else img.parent / "labels"
            if img.is_dir():
                pairs.append((img, lbl))
    return pairs


# ---- COCO -------------------------------------------------------------------------------
def download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)
    return dest


def read_coco_labels(zip_path: Path, split: str) -> dict[str, list[str]]:
    marker = f"labels/{split}2017/"
    labels = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if marker in name and name.endswith(".txt"):
                labels[Path(name).stem] = zf.read(name).decode().splitlines()
    return labels


def fetch_image(url: str, dest: Path, retries: int = 3) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                dest.write_bytes(r.read())
            return True
        except OSError:
            time.sleep(1 + attempt)
    return False


def build_coco_split(labels_zip: Path, out: Path, split: str, args: argparse.Namespace) -> int:
    labels = read_coco_labels(labels_zip, split)
    neg_ids = {COCO_NEGATIVES[c] for c in args.neg_classes}
    max_dogs = args.max_dogs if split == "train" else args.max_val_dogs
    pos, neg = select_images(labels, COCO_DOG, neg_ids, max_dogs, args.neg_ratio, args.seed)
    print(f"[{split}] {len(pos)} dog images + {len(neg)} negatives "
          f"({', '.join(args.neg_classes)}) - downloading...")
    img_dir, lbl_dir = out / "images" / split, out / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(n, convert_label_lines(labels[n], {COCO_DOG})) for n in pos] + [(n, []) for n in neg]

    def work(job: tuple[str, list[str]]) -> bool:
        name, rows = job
        ok = fetch_image(IMAGE_URL.format(split=split, name=name), img_dir / f"{name}.jpg")
        if ok:
            (lbl_dir / f"{name}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
        return ok

    done = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for ok in pool.map(work, jobs):
            done += ok
            failed += not ok
            if (done + failed) % 200 == 0:
                print(f"  {done + failed}/{len(jobs)}")
    if failed:
        print(f"  warning: {failed} images could not be downloaded (skipped)")
    return done


# ---- your own datasets ------------------------------------------------------------------
def merge_extra(root: Path, out: Path) -> int:
    names = read_names(root / "data.yaml") if (root / "data.yaml").exists() else ["dog"]
    dog_ids = {i for i, n in enumerate(names) if n.lower() == "dog"} or ({0} if len(names) == 1 else set())
    if not dog_ids:
        raise ValueError(f"{root}/data.yaml has no 'dog' class: {names}")
    copied = 0
    for split in ("train", "val"):
        for img_dir, lbl_dir in find_split_dirs(root, split):
            for img in img_dir.iterdir():
                if img.suffix.lower() not in IMAGE_EXTS:
                    continue
                src_lbl = lbl_dir / f"{img.stem}.txt"
                lines = src_lbl.read_text().splitlines() if src_lbl.exists() else []
                stem = f"extra_{root.name}_{img.stem}"
                shutil.copy2(img, out / "images" / split / f"{stem}{img.suffix.lower()}")
                rows = convert_label_lines(lines, dog_ids)
                (out / "labels" / split / f"{stem}.txt").write_text(
                    "\n".join(rows) + ("\n" if rows else ""))
                copied += 1
    print(f"[extra] merged {copied} images from {root}")
    return copied


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("datasets/dogs"))
    p.add_argument("--splits", nargs="+", default=["train", "val"], choices=["train", "val"])
    p.add_argument("--max-dogs", type=int, default=None, help="limit train dog images")
    p.add_argument("--max-val-dogs", type=int, default=None, help="limit val dog images")
    p.add_argument("--neg-ratio", type=float, default=0.3, help="negatives per dog image")
    p.add_argument("--neg-classes", nargs="*", default=["person", "cat"],
                   choices=sorted(COCO_NEGATIVES))
    p.add_argument("--extra", type=Path, nargs="*", default=[], help="your YOLO datasets")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cache", type=Path, default=Path("datasets/_cache"))
    args = p.parse_args(argv)

    labels_zip = download(LABELS_URL, args.cache / "coco2017labels.zip")
    for split in args.splits:
        build_coco_split(labels_zip, args.out, split, args)
    for split in ("train", "val"):
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)
    for extra in args.extra:
        merge_extra(extra, args.out)
    print(f"Dataset ready: {write_data_yaml(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
