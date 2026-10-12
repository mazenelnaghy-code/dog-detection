import pytest

from dog_repeller.config import ZoneConfig
from dog_repeller.domain import Detection, ThreatLevel
from dog_repeller.zone import DangerZone, box_center, estimate_distance, frame_level

W, H = 640, 480


def det(x1, y1, x2, y2, conf=0.9):
    return Detection((x1, y1, x2, y2), conf)


def test_box_center():
    assert box_center((10, 20, 30, 60)) == (20, 40)


def test_estimate_distance_pinhole():
    # 0.5 m tall dog, focal 500 px, 100 px tall box -> 2.5 m
    assert estimate_distance(100, 500, 0.5) == pytest.approx(2.5)


@pytest.mark.parametrize("h_px,focal", [(0, 500), (-5, 500), (100, None), (100, 0)])
def test_estimate_distance_unavailable(h_px, focal):
    assert estimate_distance(h_px, focal, 0.5) is None


def test_pixel_rect():
    zone = DangerZone(ZoneConfig(rect=[0.25, 0.5, 0.75, 1.0]))
    assert zone.pixel_rect(W, H) == (160, 240, 480, 480)


def test_zone_rule_uses_center_dot():
    zone = DangerZone(ZoneConfig(rect=[0.25, 0.5, 0.75, 1.0], rule="zone"))
    inside, outside = det(250, 300, 350, 400), det(0, 0, 100, 100)
    t_in, t_out = zone.assess([inside, outside], W, H)
    assert t_in.in_zone and t_in.dangerous and t_in.center == (300, 350)
    assert not t_out.in_zone and not t_out.dangerous


def _focal_zone(rule):
    # zone covers only the top-left corner so the two rules can disagree
    return DangerZone(
        ZoneConfig(rect=[0.0, 0.0, 0.1, 0.1], rule=rule, focal_length_px=500,
                   dog_height_m=0.5, danger_distance_m=3.0)
    )


def test_distance_rule():
    close = det(300, 200, 400, 400)  # 200 px tall -> 1.25 m
    far = det(300, 200, 340, 250)  # 50 px tall -> 5 m
    t_close, t_far = _focal_zone("distance").assess([close, far], W, H)
    assert t_close.distance_m == pytest.approx(1.25) and t_close.dangerous
    assert t_far.distance_m == pytest.approx(5.0) and not t_far.dangerous


def test_either_and_both_rules():
    close_outside_zone = det(300, 200, 400, 400)
    assert _focal_zone("either").assess([close_outside_zone], W, H)[0].dangerous
    assert not _focal_zone("both").assess([close_outside_zone], W, H)[0].dangerous


def test_distance_rule_without_calibration_never_dangerous():
    zone = DangerZone(ZoneConfig(rule="distance", focal_length_px=None))
    (t,) = zone.assess([det(200, 200, 400, 470)], W, H)
    assert t.distance_m is None and not t.dangerous


def test_frame_level():
    zone = DangerZone(ZoneConfig(rect=[0.25, 0.5, 0.75, 1.0], rule="zone"))
    assert frame_level([]) == ThreatLevel.CLEAR
    assert frame_level(zone.assess([det(0, 0, 50, 50)], W, H)) == ThreatLevel.DETECTED
    both = zone.assess([det(0, 0, 50, 50), det(250, 300, 350, 400)], W, H)
    assert frame_level(both) == ThreatLevel.DANGER
