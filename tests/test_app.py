import itertools

import cv2
import numpy as np
import pytest

from dog_repeller.app import App, build_parser, config_from_args
from dog_repeller.config import apply_overrides, load_config
from dog_repeller.dashboard import DashboardState
from dog_repeller.domain import Detection
from dog_repeller.hardware import Buzzer, Repeller, SimPin

W, H = 640, 480
IN_ZONE = Detection((280, 300, 360, 420), 0.9)  # centre (320, 360) is inside the default zone
FAR_AWAY = Detection((10, 40, 60, 90), 0.8)  # top-left corner, outside the zone


class ListSource:
    is_live = False

    def __init__(self, n):
        self.n, self.closed = n, False

    def read(self):
        if self.n <= 0:
            return None
        self.n -= 1
        return np.zeros((H, W, 3), np.uint8)

    def close(self):
        self.closed = True


class FakeDetector:
    def __init__(self, per_frame):
        self.per_frame = per_frame

    def detect(self, frame):
        return list(self.per_frame)


def make_app(dets, frames=10, dashboard=None, **overrides):
    cfg = apply_overrides(load_config(None), {
        "display.window": False, "controller.window_frames": 3, "controller.confirm_frames": 2,
        "buzzer.mode": "detect", **overrides})
    rep_pin, buz_pin = SimPin("rep"), SimPin("buz")
    clock = itertools.count(0, 0.1).__next__
    app = App(cfg, FakeDetector(dets), ListSource(frames), Buzzer(buz_pin, cfg.buzzer),
              Repeller(rep_pin), dashboard, clock=clock)
    return app, rep_pin, buz_pin


def test_dog_in_zone_turns_repeller_on_and_beeps():
    app, rep, buz = make_app([IN_ZONE])
    assert app.step() and not rep.is_active  # 1 frame: not confirmed yet
    assert app.step() and rep.is_active  # 2 of 3 frames: confirmed -> ON
    assert len(buz.blinks) == 1
    assert app.controller.total_bursts == 1


def test_far_dog_beeps_but_does_not_repel():
    app, rep, buz = make_app([FAR_AWAY])
    for _ in range(5):
        app.step()
    assert not rep.is_active and len(buz.blinks) == 1


def test_source_end_and_close_are_fail_safe():
    app, rep, _ = make_app([IN_ZONE], frames=3)
    while app.step():
        pass
    assert rep.is_active  # burst still running when the video ended
    app.close()
    assert not rep.is_active and app.source.closed


def test_dashboard_gets_frames_and_commands_apply():
    state = DashboardState()
    app, rep, _ = make_app([], dashboard=state)
    state.push_command("disarm")
    app.step()
    status = state.status()
    assert status["armed"] is False and status["dogs"] == 0
    assert state.wait_frame(-1, timeout=0.05)[1] is None  # nobody watching: no JPEG work
    state.viewers = 1
    app.step()
    assert state.wait_frame(-1, timeout=0.1)[1][:2] == b"\xff\xd8"  # JPEG magic
    state.push_command("test")
    app.step()
    assert rep.is_active  # manual test works even while disarmed


def test_cli_flags_map_to_config(tmp_path):
    args = build_parser().parse_args(
        ["--source", "dog.mp4", "--sim", "--no-window", "--no-dashboard", "--loop",
         "--set", "zone.rule=zone", "--set", "controller.burst_s=2"])
    cfg = config_from_args(args)
    assert cfg.camera.source == "dog.mp4" and cfg.camera.loop
    assert cfg.hardware.backend == "sim"
    assert not cfg.display.window and not cfg.dashboard.enabled
    assert cfg.zone.rule == "zone" and cfg.controller.burst_s == 2.0


def test_cli_bad_set_raises():
    with pytest.raises(ValueError):
        config_from_args(build_parser().parse_args(["--set", "nonsense"]))


def test_live_camera_loss_raises_so_service_restarts():
    from dog_repeller.app import CameraLost

    app, rep, _ = make_app([IN_ZONE], frames=3)
    app.source.is_live = True
    with pytest.raises(CameraLost):
        app.run()
    assert not rep.is_active  # still switched off on the way out


def test_dashboard_failure_does_not_stop_protection(monkeypatch):
    import dog_repeller.app as app_mod

    def boom(*a, **k):
        raise OSError("port in use")

    monkeypatch.setattr(app_mod, "start_dashboard", boom)
    app, _, _ = make_app([IN_ZONE], frames=4, dashboard=DashboardState())
    app.run()  # must not raise
    assert app.controller.total_bursts == 1


def test_record_writes_a_video(tmp_path):
    out = tmp_path / "run.avi"
    cfg_app, _, _ = make_app([IN_ZONE], frames=5)
    app = App(cfg_app.cfg, FakeDetector([IN_ZONE]), ListSource(5), cfg_app.buzzer, cfg_app.repeller,
              clock=itertools.count(0, 0.1).__next__, record=out)
    while app.step():
        pass
    app.close()
    assert cv2.VideoCapture(str(out)).get(cv2.CAP_PROP_FRAME_COUNT) >= 5
