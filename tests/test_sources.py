import itertools

import cv2
import numpy as np
import pytest

from dog_repeller.config import CameraConfig
from dog_repeller.sources import LatestFrameReader, open_source, parse_source


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("0", ("webcam", 0)),
        (1, ("webcam", 1)),
        ("picamera", ("picamera", "picamera")),
        ("rtsp://cam.local/stream", ("url", "rtsp://cam.local/stream")),
        ("videos/dog.mp4", ("file", "videos/dog.mp4")),
    ],
)
def test_parse_source(spec, expected):
    assert parse_source(spec) == expected


def _write_video(path, n=5, size=(64, 48)):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, size)
    for i in range(n):
        writer.write(np.full((size[1], size[0], 3), i * 40, np.uint8))
    writer.release()


def _drain(src, limit=100):
    frames = []
    while len(frames) < limit and (f := src.read()) is not None:
        frames.append(f)
    return frames


def test_video_file_reads_all_frames_then_none(tmp_path):
    _write_video(tmp_path / "v.avi")
    src = open_source(CameraConfig(source=str(tmp_path / "v.avi")))
    assert len(_drain(src)) == 5 and not src.is_live
    src.close()


def test_video_file_loop(tmp_path):
    _write_video(tmp_path / "v.avi")
    src = open_source(CameraConfig(source=str(tmp_path / "v.avi"), loop=True))
    assert len(_drain(src, limit=12)) == 12
    src.close()


def test_image_folder_and_rotation(tmp_path):
    for i in range(3):
        cv2.imwrite(str(tmp_path / f"{i}.png"), np.zeros((40, 60, 3), np.uint8))
    (tmp_path / "notes.txt").write_text("ignored")
    frames = _drain(open_source(CameraConfig(source=str(tmp_path), rotate=90)))
    assert len(frames) == 3 and frames[0].shape == (60, 40, 3)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_source(CameraConfig(source=str(tmp_path / "nope.mp4")))


def test_latest_frame_reader_returns_new_frames_then_none():
    counter = itertools.count()

    def grab():
        i = next(counter)
        return np.full((2, 2), i, np.uint8) if i < 3 else None

    closed = []
    reader = LatestFrameReader(grab, lambda: closed.append(True), give_up_s=0.2, timeout_s=1)
    frames = _drain(reader)
    assert 1 <= len(frames) <= 3  # newest-frame semantics may skip frames
    assert frames[-1][0, 0] == 2
    reader.close()
    assert closed == [True]


def test_picamera_source_uses_bgr_format_framerate_and_stops(monkeypatch):
    import sys
    import types

    calls = {}

    class FakePicamera2:
        def create_video_configuration(self, main, controls):
            calls["main"], calls["controls"] = main, controls
            return "cfg"

        def configure(self, cfg):
            calls["configured"] = cfg

        def start(self):
            calls["started"] = True

        def capture_array(self, name):
            calls["stream"] = name
            return np.zeros((48, 64, 3), np.uint8)

        def stop(self):
            calls["stopped"] = True

        def close(self):
            calls["closed"] = True

    monkeypatch.setitem(sys.modules, "picamera2", types.SimpleNamespace(Picamera2=FakePicamera2))
    src = open_source(CameraConfig(source="picamera", width=64, height=48, fps=40))
    frame = src.read()
    src.close()
    assert frame.shape == (48, 64, 3) and src.is_live
    assert calls["main"] == {"size": (64, 48), "format": "RGB888"}
    assert calls["controls"] == {"FrameRate": 40}
    assert calls["stream"] == "main" and calls["stopped"] and calls["closed"]
