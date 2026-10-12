import cv2
import numpy as np
import pytest

from dog_repeller.domain import Detection
from tools.evaluate import Score, list_images, run, simulate

IMG = np.random.default_rng(1).integers(0, 255, (120, 160, 3), dtype=np.uint8)


@pytest.mark.parametrize("variant", ["none", "night", "far", "blur"])
def test_simulate_keeps_shape(variant):
    out = simulate(IMG, variant)
    assert out.shape == IMG.shape and out.dtype == np.uint8


def test_night_is_gray_and_darker():
    out = simulate(IMG, "night")
    assert np.array_equal(out[..., 0], out[..., 1]) and out.mean() < IMG.mean()


def test_far_shrinks_content_onto_grey_border():
    out = simulate(IMG, "far")
    assert (out[0, 0] == 114).all() and (out[60, 80] != 114).any()


def test_unknown_variant():
    with pytest.raises(ValueError):
        simulate(IMG, "fog")


def test_score_counts():
    s = Score()
    s.add("a", True, True, 0.01)
    s.add("b", True, False, 0.01)
    s.add("c", False, True, 0.02)
    s.add("d", False, False, 0.02)
    assert (s.recall, s.false_alarm_rate) == (0.5, 0.5)
    assert s.missed == ["b"] and s.alarms == ["c"]
    assert s.ms_per_frame == pytest.approx(15)


class AlwaysDog:
    def detect(self, img):
        return [Detection((1, 1, 20, 20), 0.9)]


def test_run_and_save_failures(tmp_path):
    for folder in ("dogs", "no_dogs"):
        (tmp_path / folder).mkdir()
        cv2.imwrite(str(tmp_path / folder / "x.png"), IMG)
    (tmp_path / "dogs" / "readme.txt").write_text("not an image")
    dogs, no_dogs = list_images(tmp_path / "dogs"), list_images(tmp_path / "no_dogs")
    s = run(AlwaysDog(), dogs, no_dogs, "none", tmp_path / "out")
    assert (s.dogs_found, s.false_alarms) == (1, 1)
    assert (tmp_path / "out" / "false_alarms" / "none_x.jpg").exists()
