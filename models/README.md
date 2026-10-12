# models/

Model files live here but are **not committed** (they are large and can be re-created).

| File | How to get it |
|---|---|
| `yolo11n_ncnn_model/` | `python training/export.py --weights yolo11n.pt --format ncnn --imgsz 640 --out models` (done by `deploy/setup_pi.sh`) |
| `dog_yolo11n.pt` | `python training/train.py ...` or the Colab notebook |
| `dog_yolo11n_ncnn_model/` | `python training/export.py --weights models/dog_yolo11n.pt --format ncnn --imgsz 640` |

`yolo11n.pt` (COCO-pretrained) is downloaded automatically by Ultralytics the first time it is used.
