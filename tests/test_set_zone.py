import pytest
import yaml

from dog_repeller.config import load_config
from tools.set_zone import roi_to_rect, write_rect


def test_roi_to_rect():
    assert roi_to_rect((64, 240, 512, 240), 640, 480) == [0.1, 0.5, 0.9, 1.0]
    assert roi_to_rect((600, 0, 100, 10), 640, 480)[2] == 1.0  # clipped to the frame


def test_empty_selection():
    with pytest.raises(ValueError):
        roi_to_rect((0, 0, 0, 0), 640, 480)


def test_write_rect_keeps_other_settings(tmp_path):
    cfg = tmp_path / "local.yaml"
    cfg.write_text("base: ../config/pi.yaml\ndashboard:\n  token: abc\n")
    write_rect(cfg, [0.1, 0.5, 0.9, 1.0])
    data = yaml.safe_load(cfg.read_text())
    assert data["dashboard"]["token"] == "abc" and data["zone"]["rect"] == [0.1, 0.5, 0.9, 1.0]


def test_written_rect_loads(tmp_path):
    cfg = tmp_path / "c.yaml"
    write_rect(cfg, [0.25, 0.4, 0.75, 1.0])
    assert load_config(cfg).zone.rect == [0.25, 0.4, 0.75, 1.0]
