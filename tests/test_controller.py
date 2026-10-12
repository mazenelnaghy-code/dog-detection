from dog_repeller.config import BuzzerConfig, ControllerConfig
from dog_repeller.controller import Controller, State
from dog_repeller.domain import ThreatLevel

CLEAR, DETECTED, DANGER = ThreatLevel.CLEAR, ThreatLevel.DETECTED, ThreatLevel.DANGER


def make(mode="off", **kw):
    cfg = dict(window_frames=3, confirm_frames=2, burst_s=2.0, cooldown_s=1.0,
               max_bursts=2, lockout_s=10.0, start_armed=True)
    cfg.update(kw)
    return Controller(ControllerConfig(**cfg), BuzzerConfig(mode=mode, min_interval_s=5.0))


def feed(ctrl, levels, start=0.0, dt=0.1):
    """Feed one level per frame, dt seconds apart. Returns (commands, end_time)."""
    t, out = start, []
    for lvl in levels:
        out.append(ctrl.update(lvl, t))
        t += dt
    return out, t


def test_single_frame_does_not_trigger():
    c = make()
    cmds, _ = feed(c, [DANGER, CLEAR, CLEAR])
    assert not any(x.repeller_on for x in cmds)
    assert c.state is State.IDLE


def test_confirmed_danger_starts_burst():
    c = make()
    cmds, _ = feed(c, [DANGER, DANGER])
    assert [x.repeller_on for x in cmds] == [False, True]
    assert c.state is State.REPELLING


def test_detected_only_never_repels():
    c = make()
    cmds, _ = feed(c, [DETECTED] * 10)
    assert not any(x.repeller_on for x in cmds)


def test_burst_cooldown_reburst_then_lockout():
    c = make()
    c.update(DANGER, 0.0)
    assert c.update(DANGER, 0.1).repeller_on  # burst 1 until t=2.1
    assert c.update(DANGER, 2.0).repeller_on
    assert not c.update(DANGER, 2.2).repeller_on and c.state is State.COOLDOWN
    assert c.update(DANGER, 3.3).repeller_on  # burst 2 (cooldown ended at 3.2)
    assert not c.update(DANGER, 5.4).repeller_on and c.state is State.LOCKOUT
    assert not c.update(DANGER, 10.0).repeller_on  # still resting
    c.update(DANGER, 15.5)  # lockout over -> idle
    assert c.update(DANGER, 15.6).repeller_on  # a new episode may start


def test_cooldown_without_danger_returns_to_idle():
    c = make()
    feed(c, [DANGER, DANGER])
    feed(c, [CLEAR] * 3, start=2.2)
    c.update(CLEAR, 3.5)
    assert c.state is State.IDLE and c.bursts == 0


def test_disarm_stops_immediately_and_blocks():
    c = make()
    feed(c, [DANGER, DANGER])
    c.disarm()
    assert not c.update(DANGER, 0.3).repeller_on
    cmds, _ = feed(c, [DANGER] * 5, start=0.4)
    assert not any(x.repeller_on for x in cmds)
    c.arm()
    assert c.update(DANGER, 1.0).repeller_on


def test_start_disarmed():
    c = make(start_armed=False)
    cmds, _ = feed(c, [DANGER] * 5)
    assert not any(x.repeller_on for x in cmds)


def test_manual_test_burst_works_without_dog_and_ends():
    c = make(start_armed=False)
    c.request_test()
    assert c.update(CLEAR, 0.0).repeller_on and c.testing
    assert c.update(CLEAR, 1.9).repeller_on
    assert not c.update(CLEAR, 2.1).repeller_on
    assert c.state is State.IDLE
    assert c.total_bursts == 0  # tests are not counted as real triggers


def test_beep_detect_mode_rising_edge_and_rate_limit():
    c = make(mode="detect")
    cmds, t = feed(c, [DETECTED, DETECTED, DETECTED])
    assert [x.beep for x in cmds] == [False, True, False]
    cmds, t = feed(c, [CLEAR] * 3 + [DETECTED] * 2, start=t)  # back within 5 s: silent
    assert not any(x.beep for x in cmds)
    cmds, _ = feed(c, [CLEAR] * 3 + [DETECTED] * 2, start=10.0)  # after 5 s: beeps again
    assert any(x.beep for x in cmds)


def test_beep_danger_mode_ignores_far_dogs():
    c = make(mode="danger")
    cmds, t = feed(c, [DETECTED] * 4)
    assert not any(x.beep for x in cmds)
    cmds, _ = feed(c, [DANGER] * 2, start=t)
    assert any(x.beep for x in cmds)


def test_beep_off_and_disarmed_are_silent():
    assert not any(x.beep for x in feed(make(mode="off"), [DANGER] * 4)[0])
    c = make(mode="detect", start_armed=False)
    assert not any(x.beep for x in feed(c, [DANGER] * 4)[0])


def test_snapshot_fields():
    c = make()
    feed(c, [DANGER, DANGER])
    snap = c.snapshot(0.2)
    assert snap["state"] == "repelling"
    assert snap["armed"] is True
    assert snap["level"] == "DANGER"
    assert snap["total_bursts"] == 1
    assert 0 < snap["seconds_left"] <= 2.0
