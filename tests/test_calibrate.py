import pytest

from dog_repeller.zone import estimate_distance
from tools.calibrate_focal import CAMERAS, focal_from_measurement, focal_from_specs, main


def test_measurement_round_trip_with_distance_estimate():
    focal = focal_from_measurement(pixel_height=175, distance_m=3, real_height_m=1.75)
    assert focal == pytest.approx(300)
    assert estimate_distance(175, focal, 1.75) == pytest.approx(3)


def test_measurement_rejects_zero():
    with pytest.raises(ValueError):
        focal_from_measurement(0, 3, 1.75)


def test_pi_camera_v2_spec():
    assert focal_from_specs(*CAMERAS["picam-v2"], 640) == pytest.approx(528.7, abs=0.1)


def test_cli_prints_config_line(capsys):
    assert main(["spec", "--camera", "picam-v2", "--width", "640"]) == 0
    assert "focal_length_px: 528.7" in capsys.readouterr().out
