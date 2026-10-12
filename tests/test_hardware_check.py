from pathlib import Path

from dog_repeller.config import BuzzerConfig, CameraConfig
from dog_repeller.hardware import Buzzer, Repeller, SimPin
from tools.hardware_check import FAIL, PASS, WARN, check_camera, check_outputs, check_system

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_system_check_runs_anywhere():
    status, msg = check_system()
    assert status in (PASS, WARN) and "Python" in msg


def test_camera_check_with_image_folder(tmp_path):
    snap = tmp_path / "snap.jpg"
    status, msg = check_camera(CameraConfig(source=str(SAMPLES / "dogs")), snap, frames=3)
    assert status == PASS and snap.exists() and "3 frames" in msg


def test_camera_check_reports_missing_camera(tmp_path):
    status, msg = check_camera(CameraConfig(source=str(tmp_path / "nope.mp4")), tmp_path / "s.jpg")
    assert status == FAIL and "cannot open" in msg


def test_outputs_check_answers(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    buzz_pin, rep_pin = SimPin("b"), SimPin("r")
    answers = iter([True, False])
    res = dict(check_outputs(Buzzer(buzz_pin, BuzzerConfig()), Repeller(rep_pin),
                             lambda q: next(answers)))
    assert res["Buzzer"][0] == PASS and res["Repeller"][0] == FAIL
    assert len(buzz_pin.blinks) == 1 and not rep_pin.is_active  # relay left OFF
    res = dict(check_outputs(Buzzer(SimPin("b"), BuzzerConfig()), Repeller(SimPin("r")),
                             lambda q: None))
    assert res["Buzzer"][0] == WARN  # not confirmed (--yes)
