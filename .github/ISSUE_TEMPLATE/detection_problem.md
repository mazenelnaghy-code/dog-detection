---
name: Missed dog / false alarm
about: The model missed a dog, or fired on a child, cat or something else
labels: detection
---

**Missed dog or false alarm?**

**Photo / video frame** (attach it - avoid photos where children can be identified):

**Settings** (`model.path`, `model.imgsz`, `model.conf`, `model.also_count`, `zone.rect`):

**Output of** `python tools/evaluate.py --dogs <folder> --no-dogs <folder> --save-failures failures/`:
