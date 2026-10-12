import time

import cv2
import numpy as np

from dog_repeller.config import CameraConfig
from dog_repeller.demo import FPS, SIZE, build_demo_video, demo_overrides, letterbox
from dog_repeller.sources import open_source


def test_letterbox_keeps_canvas_size():
    img = np.zeros((100, 300, 3), np.uint8)
    for scale, y in ((1.0, 0.5), (0.25, 0.0), (0.25, 1.0)):
        assert letterbox(img, scale=scale, y_frac=y).shape == (SIZE[1], SIZE[0], 3)


def test_demo_video_is_built_from_samples(tmp_path):
    path = build_demo_video(tmp_path / "demo.avi")
    cap = cv2.VideoCapture(str(path))
    assert cap.get(cv2.CAP_PROP_FPS) == FPS
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == int(19.5 * FPS)
    overrides = demo_overrides(path)
    assert overrides["hardware.backend"] == "sim" and overrides["camera.realtime"] is True


def _video(path, n, fps):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24))
    for i in range(n):
        w.write(np.full((24, 32, 3), i * 10, np.uint8))
    w.release()


def test_realtime_playback_takes_real_time(tmp_path):
    _video(tmp_path / "v.avi", 6, 50)  # 6 frames at 50 fps = 0.1 s
    src = open_source(CameraConfig(source=str(tmp_path / "v.avi"), realtime=True))
    t0 = time.monotonic()
    n = 0
    while src.read() is not None:
        n += 1
    assert n == 6 and time.monotonic() - t0 >= 0.09


def test_realtime_playback_skips_frames_when_slow(tmp_path):
    _video(tmp_path / "v.avi", 20, 50)  # 0.4 s of video
    src = open_source(CameraConfig(source=str(tmp_path / "v.avi"), realtime=True))
    n = 0
    while src.read() is not None:
        n += 1
        time.sleep(0.06)  # "detector" slower than 50 fps -> frames must be dropped
    assert n < 12
