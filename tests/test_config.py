from pathlib import Path

import pytest

from dog_repeller.config import Config, apply_overrides, load_config

ROOT = Path(__file__).resolve().parents[1]


def test_defaults_without_file():
    cfg = load_config(None)
    assert isinstance(cfg, Config)
    assert cfg.model.path == "yolo11n.pt"
    assert cfg.repeller.pin == 17
    assert cfg.buzzer.pin == 27
    assert cfg.hardware.backend == "sim"


def test_shipped_configs_load():
    pc = load_config(ROOT / "config" / "default.yaml")
    pi = load_config(ROOT / "config" / "pi.yaml")
    assert pc.hardware.backend == "sim"
    assert pi.hardware.backend == "gpio"
    assert pi.camera.source == "picamera"
    # pi.yaml inherits everything it does not override from default.yaml
    assert pi.controller.burst_s == pc.controller.burst_s


def test_base_inheritance_merges_nested(tmp_path):
    (tmp_path / "base.yaml").write_text("model:\n  conf: 0.3\n  imgsz: 416\n")
    (tmp_path / "child.yaml").write_text("base: base.yaml\nmodel:\n  conf: 0.6\n")
    cfg = load_config(tmp_path / "child.yaml")
    assert cfg.model.conf == 0.6
    assert cfg.model.imgsz == 416


def test_numeric_source_becomes_string(tmp_path):
    (tmp_path / "c.yaml").write_text("camera:\n  source: 0\n")
    assert load_config(tmp_path / "c.yaml").camera.source == "0"


def test_dotted_overrides():
    cfg = apply_overrides(load_config(None), {"camera.source": "dog.mp4", "zone.rule": "zone"})
    assert cfg.camera.source == "dog.mp4"
    assert cfg.zone.rule == "zone"


@pytest.mark.parametrize(
    "text",
    [
        "camera:\n  bogus: 1\n",
        "nonsense: 1\n",
        "zone:\n  rect: [0.8, 0.1, 0.2, 0.9]\n",
        "zone:\n  rect: [0.0, 0.0, 1.5, 1.0]\n",
        "zone:\n  rule: sometimes\n",
        "buzzer:\n  mode: loud\n",
        "hardware:\n  backend: arduino\n",
        "controller:\n  confirm_frames: 9\n  window_frames: 3\n",
    ],
)
def test_invalid_config_raises(tmp_path, text):
    (tmp_path / "bad.yaml").write_text(text)
    with pytest.raises(ValueError):
        load_config(tmp_path / "bad.yaml")


def test_unknown_override_raises():
    with pytest.raises(ValueError):
        apply_overrides(load_config(None), {"camera.nope": 1})


def test_also_count_defaults_and_validation(tmp_path):
    cfg = load_config(None)
    assert "cow" in cfg.model.also_count and "cat" not in cfg.model.also_count
    assert apply_overrides(cfg, {"model.also_count": ["cow"]}).model.also_count == ["cow"]
    for bad in (["cat"], ["Person", "cow"]):
        with pytest.raises(ValueError):
            apply_overrides(cfg, {"model.also_count": bad})
    (tmp_path / "c.yaml").write_text("model:\n  also_count: cow\n")
    with pytest.raises(ValueError):
        load_config(tmp_path / "c.yaml")  # must be a list
