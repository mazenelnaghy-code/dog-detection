"""Built-in demo: try the whole system in one command, no camera or hardware needed.

    python -m dog_repeller --demo

Builds a short scene from the public-domain photos in ``samples/``: children and a street cat
(nothing must happen), then an Egyptian street dog that walks up to the camera (beep ->
repeller bursts -> cooldown -> idle when it leaves).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
FPS, SIZE = 10, (640, 480)
GREY = (118, 122, 126)


def letterbox(img: np.ndarray, size: tuple[int, int] = SIZE, scale: float = 1.0,
              y_frac: float = 0.5) -> np.ndarray:
    """Fit ``img`` into ``size`` (keeping aspect), scaled by ``scale``, placed at ``y_frac``."""
    w, h = size
    k = min(w / img.shape[1], h / img.shape[0]) * scale
    small = cv2.resize(img, (max(1, int(img.shape[1] * k)), max(1, int(img.shape[0] * k))),
                       interpolation=cv2.INTER_AREA)
    canvas = np.full((h, w, 3), GREY, np.uint8)
    y = int((h - small.shape[0]) * y_frac)
    x = (w - small.shape[1]) // 2
    canvas[y:y + small.shape[0], x:x + small.shape[1]] = small
    return canvas


def _load(name: str) -> np.ndarray:
    path = SAMPLES / name
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Demo sample missing: {path} (run from a clone of the repo)")
    return img


def build_demo_video(path: Path | None = None) -> Path:
    path = path or Path(tempfile.gettempdir()) / "dog_repeller_demo.avi"
    kids = _load("no_dogs/children_0076.jpg")
    cat = _load("no_dogs/street_cat_0085.jpg")
    dog = _load("dogs/street_dog_0077.jpg")
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, SIZE)

    def hold(frame: np.ndarray, seconds: float) -> None:
        for _ in range(int(seconds * FPS)):
            writer.write(frame)

    hold(letterbox(kids), 2.5)  # children playing: nothing may happen
    hold(letterbox(cat), 2.0)  # a street cat: nothing should happen
    steps = int(6 * FPS)
    for i in range(steps):  # the dog walks from far away (small, high) to the camera
        t = i / (steps - 1)
        writer.write(letterbox(dog, scale=0.25 + 0.75 * t, y_frac=0.1 + 0.9 * t))
    hold(letterbox(dog), 5.0)  # the dog stays close -> repeated bursts
    hold(np.full((SIZE[1], SIZE[0], 3), GREY, np.uint8), 4.0)  # it left -> cooldown -> idle
    writer.release()
    return path


def demo_overrides(video: Path) -> dict:
    return {
        "camera.source": str(video),
        "camera.realtime": True,  # play like a live camera
        "camera.loop": True,
        "camera.fps": FPS,
        "hardware.backend": "sim",
        "controller.burst_s": 3.0,
        "controller.cooldown_s": 2.0,
    }
