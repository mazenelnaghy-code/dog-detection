import numpy as np
import pytest

from dog_repeller.detector import resolve_class_ids, results_to_detections

COCO_LIKE = {0: "person", 15: "cat", 16: "dog"}


def test_resolve_class_ids_coco_and_custom():
    assert resolve_class_ids(COCO_LIKE, "dog") == [16]
    assert resolve_class_ids({0: "Dog"}, "dog") == [0]
    assert resolve_class_ids(["person", "dog"], "dog") == [1]


def test_resolve_class_ids_missing_class():
    with pytest.raises(ValueError, match="dog"):
        resolve_class_ids({0: "person"}, "dog")


def test_results_to_detections_filters_class_and_size_and_sorts():
    xyxy = np.array([[0, 0, 100, 100], [10, 10, 20, 20], [0, 0, 50, 50], [5, 5, 200, 200]], float)
    conf = np.array([0.6, 0.9, 0.8, 0.95])
    cls = np.array([16, 16, 0, 16])
    dets = results_to_detections(xyxy, conf, cls, [16], min_area_px=500)
    assert [d.conf for d in dets] == pytest.approx([0.95, 0.6])  # small box + person removed
    assert dets[1].box == (0.0, 0.0, 100.0, 100.0)


COCO_SUBSET = {0: "person", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow", 21: "bear"}


def test_also_count_adds_lookalikes_but_keeps_dog_first():
    ids = resolve_class_ids(COCO_SUBSET, "dog", ["bear", "cow", "sheep", "horse", "zebra"])
    assert ids[0] == 16 and set(ids) == {16, 17, 18, 19, 21}  # zebra absent -> ignored
    assert 0 not in ids and 15 not in ids  # never person / cat


def test_also_count_ignored_for_single_class_model():
    assert resolve_class_ids({0: "dog"}, "dog", ["bear", "cow"]) == [0]
