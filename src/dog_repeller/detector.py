"""YOLO dog detector (Ultralytics).

Works with any Ultralytics detection model: the COCO-pretrained ``yolo11n.pt`` / ``yolov8n.pt``
(class 16 is "dog"), our fine-tuned single-class model, or their NCNN / ONNX exports. The dog class is found
by *name*, so no class numbers are hard-coded.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np

from .config import ModelConfig
from .domain import Detection

log = logging.getLogger(__name__)


def resolve_class_ids(names: Mapping[int, str] | Sequence[str], class_name: str,
                      also_count: Iterable[str] = ()) -> list[int]:
    """Ids of ``class_name`` (required) plus any ``also_count`` classes the model happens to have."""
    items = list(names.items() if isinstance(names, Mapping) else enumerate(names))
    ids = [int(i) for i, n in items if str(n).lower() == class_name.lower()]
    if not ids:
        known = [n for _, n in items]
        raise ValueError(f"Model has no class named {class_name!r}. Its classes: {known[:20]}")
    extra = {c.lower() for c in also_count}
    return ids + [int(i) for i, n in items if str(n).lower() in extra and int(i) not in ids]


def results_to_detections(xyxy: np.ndarray, conf: np.ndarray, cls: np.ndarray,
                          class_ids: Iterable[int], min_area_px: float) -> list[Detection]:
    wanted = set(class_ids)
    out = []
    for box, score, k in zip(xyxy, conf, cls, strict=True):
        if int(k) not in wanted:
            continue
        x1, y1, x2, y2 = (float(v) for v in box)
        if (x2 - x1) * (y2 - y1) < min_area_px:
            continue
        out.append(Detection((x1, y1, x2, y2), float(score)))
    return sorted(out, key=lambda d: d.conf, reverse=True)


class DogDetector:
    def __init__(self, cfg: ModelConfig):
        from ultralytics import YOLO  # heavy import, only when a real model is needed

        path = Path(cfg.path)
        if path.suffix != ".pt" and not path.exists():
            raise FileNotFoundError(
                f"Model {cfg.path} not found. Create it with: python training/export.py "
                f"--weights yolo11n.pt --format ncnn --imgsz {cfg.imgsz} --out {path.parent}")
        self.cfg = cfg
        self.model = YOLO(cfg.path, task="detect")
        self.class_ids = resolve_class_ids(self.model.names, cfg.class_name, cfg.also_count)
        self.detect(np.zeros((cfg.imgsz, cfg.imgsz, 3), np.uint8))  # warm-up
        log.info("Loaded %s (dog class ids %s)", cfg.path, self.class_ids)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        # compete=True: every class (cat, person, ...) takes part in class-agnostic NMS, so a box
        # that is more "cat" than "dog" suppresses the weaker dog box on the same animal.
        compete = self.cfg.compete and len(self.model.names) > 1
        result = self.model.predict(frame, imgsz=self.cfg.imgsz, conf=self.cfg.conf,
                                    iou=self.cfg.iou, device=self.cfg.device,
                                    classes=None if compete else self.class_ids,
                                    agnostic_nms=compete, verbose=False)[0]
        boxes = result.boxes
        return results_to_detections(boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy(),
                                     boxes.cls.cpu().numpy(), self.class_ids,
                                     self.cfg.min_box_area * w * h)
