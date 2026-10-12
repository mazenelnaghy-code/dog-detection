"""Frame sources - the "switch" between a recorded video and the live camera.

``camera.source`` decides where frames come from:

* ``picamera``                    -> Raspberry Pi camera module (picamera2)
* ``0``, ``1`` ...                -> USB webcam index
* ``rtsp://...``, ``http://...``  -> network stream
* ``video.mp4`` / ``photo.jpg``   -> a file (great for testing at home)
* ``some/folder``                 -> every image in a folder, in name order

Files are read frame-by-frame (nothing is skipped, results are reproducible). Live sources
run a background thread and always hand out the newest frame, so a slow detector never
works on stale images.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from .config import CameraConfig

log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


class FrameSource(Protocol):
    is_live: bool

    def read(self) -> np.ndarray | None: ...  # None = no more frames

    def close(self) -> None: ...


def parse_source(spec: str | int) -> tuple[str, str | int]:
    s = str(spec).strip()
    if s.lower() in {"picamera", "picam", "csi"}:
        return ("picamera", s)
    if s.isdigit():
        return ("webcam", int(s))
    if "://" in s:
        return ("url", s)
    return ("file", s)


def open_source(cfg: CameraConfig) -> FrameSource:
    kind, value = parse_source(cfg.source)
    if kind == "picamera":
        src: FrameSource = PiCameraSource(cfg.width, cfg.height, cfg.fps)
    elif kind in {"webcam", "url"}:
        src = OpenCVLiveSource(value, cfg.width, cfg.height, cfg.fps)
    elif Path(value).is_dir():
        src = ImageFolderSource(Path(value), cfg.loop)
    else:
        src = VideoFileSource(Path(value), cfg.loop, cfg.realtime)
    return RotatedSource(src, cfg.rotate) if cfg.rotate else src


class VideoFileSource:
    is_live = False

    def __init__(self, path: Path, loop: bool = False, realtime: bool = False):
        if not path.exists():
            raise FileNotFoundError(f"Video/image not found: {path}")
        self.path, self.loop, self.realtime = path, loop, realtime
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise OSError(f"OpenCV cannot open {path}")
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        self._dt = 1.0 / fps if fps and fps > 0 else 1.0 / 30
        self._next_t: float | None = None

    def _pace(self) -> None:
        """Real-time playback: wait for the frame's time, or skip frames we are late for."""
        now = time.monotonic()
        if self._next_t is None:
            self._next_t = now
        while now > self._next_t + self._dt:  # detector slower than the video: drop frames
            if not self._cap.grab():
                break
            self._next_t += self._dt
        if self._next_t > now:
            time.sleep(self._next_t - now)
        self._next_t += self._dt

    def read(self) -> np.ndarray | None:
        if self.realtime:
            self._pace()
        ok, frame = self._cap.read()
        if not ok and self.loop:
            self._cap.release()
            self._cap = cv2.VideoCapture(str(self.path))
            ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()


class ImageFolderSource:
    is_live = False

    def __init__(self, folder: Path, loop: bool = False):
        self.files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        if not self.files:
            raise FileNotFoundError(f"No images in {folder}")
        self.loop, self._i = loop, 0

    def read(self) -> np.ndarray | None:
        while True:
            if self._i >= len(self.files):
                if not self.loop:
                    return None
                self._i = 0
            path = self.files[self._i]
            self._i += 1
            frame = cv2.imread(str(path))
            if frame is not None:
                return frame
            log.warning("Skipping unreadable image %s", path)

    def close(self) -> None:
        pass


class LatestFrameReader:
    """Calls ``grab()`` in a background thread and keeps only the newest frame."""

    is_live = True

    def __init__(self, grab: Callable[[], np.ndarray | None], on_close: Callable[[], None],
                 give_up_s: float = 10.0, timeout_s: float = 12.0):
        self._grab, self._on_close = grab, on_close
        self._give_up_s, self._timeout = give_up_s, timeout_s
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._seq = self._read_seq = 0
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="frame-grabber", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        failing_since: float | None = None
        while self._running:
            try:
                frame = self._grab()
            except Exception:  # camera unplugged, driver error, ...
                log.exception("Camera read failed")
                frame = None
            if frame is None:
                now = time.monotonic()
                failing_since = failing_since or now
                if now - failing_since >= self._give_up_s:  # short hiccups are tolerated
                    log.error("Camera delivered no frames for %.0f s", self._give_up_s)
                    break
                time.sleep(0.05)
                continue
            failing_since = None
            with self._cond:
                self._frame, self._seq = frame, self._seq + 1
                self._cond.notify_all()
        with self._cond:
            self._running = False
            self._cond.notify_all()

    def read(self) -> np.ndarray | None:
        with self._cond:
            self._cond.wait_for(lambda: self._seq != self._read_seq or not self._running,
                                self._timeout)
            if self._seq == self._read_seq:
                return None
            self._read_seq = self._seq
            return self._frame

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=5)
        if self._thread.is_alive():  # still blocked inside the driver: releasing now could crash
            log.warning("Camera thread did not stop; leaving the device to the OS")
            return
        self._on_close()


class OpenCVLiveSource(LatestFrameReader):
    def __init__(self, source: str | int, width: int, height: int, fps: int):
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise OSError(f"Cannot open camera/stream {source!r}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        def grab() -> np.ndarray | None:
            ok, frame = cap.read()
            return frame if ok else None

        super().__init__(grab, cap.release)


class PiCameraSource(LatestFrameReader):
    def __init__(self, width: int, height: int, fps: int = 30):
        from picamera2 import Picamera2  # only available on Raspberry Pi OS

        cam = Picamera2()
        # "RGB888" is stored B,G,R in memory - exactly what OpenCV and Ultralytics expect.
        # FrameRate also caps the exposure time (<= 1/fps), which reduces motion blur on
        # running dogs.
        cam.configure(cam.create_video_configuration(main={"size": (width, height),
                                                           "format": "RGB888"},
                                                     controls={"FrameRate": fps}))
        cam.start()

        def stop() -> None:
            cam.stop()
            cam.close()

        super().__init__(lambda: cam.capture_array("main"), stop)


class RotatedSource:
    def __init__(self, inner: FrameSource, degrees: int):
        self.inner, self._code = inner, _ROTATIONS[degrees]
        self.is_live = inner.is_live

    def read(self) -> np.ndarray | None:
        frame = self.inner.read()
        return None if frame is None else cv2.rotate(frame, self._code)

    def close(self) -> None:
        self.inner.close()
