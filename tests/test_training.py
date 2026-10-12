import yaml

from training.prepare_coco_dogs import (
    classes_in,
    convert_label_lines,
    find_split_dirs,
    merge_extra,
    select_images,
    write_data_yaml,
)

DOG = "16 0.5 0.5 0.2 0.3"
PERSON = "0 0.1 0.1 0.05 0.2"
CAT = "15 0.4 0.4 0.1 0.1"
CAR = "2 0.3 0.3 0.1 0.1"


def test_classes_and_conversion():
    assert classes_in([DOG, PERSON, ""]) == {16, 0}
    assert convert_label_lines([DOG, PERSON, DOG], {16}) == ["0 0.5 0.5 0.2 0.3"] * 2


def test_select_images_positives_and_hard_negatives():
    labels = {f"d{i}": [DOG, PERSON] for i in range(10)}
    labels |= {f"p{i}": [PERSON] for i in range(10)}
    labels |= {f"c{i}": [CAT] for i in range(3)}
    labels |= {"car": [CAR], "empty": []}
    pos, neg = select_images(labels, 16, {0, 15}, max_dogs=4, neg_ratio=0.5, seed=1)
    assert len(pos) == 4 and all(n.startswith("d") for n in pos)
    assert len(neg) == 2 and all(n[0] in "pc" for n in neg)  # never cars / empty / dogs
    assert select_images(labels, 16, {0, 15}, 4, 0.5, seed=1) == (pos, neg)  # reproducible


def test_write_data_yaml(tmp_path):
    data = yaml.safe_load(write_data_yaml(tmp_path).read_text())
    assert data["names"] == {0: "dog"} and data["train"] == "images/train"


def test_merge_roboflow_style_extra(tmp_path):
    extra = tmp_path / "street_dogs"
    for split in ("train", "valid"):
        (extra / split / "images").mkdir(parents=True)
        (extra / split / "labels").mkdir(parents=True)
        (extra / split / "images" / "a.jpg").write_bytes(b"jpg")
        (extra / split / "labels" / "a.txt").write_text("1 0.5 0.5 0.3 0.3\n0 0.2 0.2 0.1 0.1\n")
    (extra / "data.yaml").write_text("names: ['person', 'dog']\n")
    assert [p[0].parent.name for p in find_split_dirs(extra, "val")] == ["valid"]

    out = tmp_path / "out"
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)
    assert merge_extra(extra, out) == 2
    label = (out / "labels" / "val" / "extra_street_dogs_a.txt").read_text()
    assert label == "0 0.5 0.5 0.3 0.3\n"  # dog (id 1) -> 0, person dropped
