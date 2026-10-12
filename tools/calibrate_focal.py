"""Find the camera focal length in pixels, needed for distance estimation (zone.focal_length_px).

Pinhole camera: an object of real height H at distance D appears h pixels tall, h = f * H / D,
so f = h * D / H.

Option A - measure (most accurate). Stand a person (or put any object) at a known distance and
take a photo with the SAME camera and resolution the system uses:

    python tools/calibrate_focal.py measure --image me_at_3m.jpg --distance 3 --real-height 1.75
    python tools/calibrate_focal.py measure --pixel-height 182 --distance 3 --real-height 1.75

(with --image, YOLO finds the tallest person / dog / --class in the photo and measures it)

Option B - from the camera datasheet (quick estimate):

    python tools/calibrate_focal.py spec --camera picam-v2 --width 640

Then put the printed value in your config:   zone: { focal_length_px: <value> }
"""

from __future__ import annotations

import argparse
import sys

# focal length (mm), sensor width (mm) of common Raspberry Pi cameras
CAMERAS = {
    "picam-v1": (3.60, 3.76),  # OV5647
    "picam-v2": (3.04, 3.68),  # Sony IMX219 (also the NoIR v2)
    "picam-v3": (4.74, 6.45),  # Sony IMX708
    "picam-v3-wide": (2.75, 6.45),
}


def focal_from_measurement(pixel_height: float, distance_m: float, real_height_m: float) -> float:
    if min(pixel_height, distance_m, real_height_m) <= 0:
        raise ValueError("pixel height, distance and real height must all be positive")
    return pixel_height * distance_m / real_height_m


def focal_from_specs(focal_mm: float, sensor_width_mm: float, image_width_px: int) -> float:
    return focal_mm * image_width_px / sensor_width_mm


def measure_box_height(image_path: str, class_name: str, model_path: str) -> float:
    import cv2
    from ultralytics import YOLO

    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(image_path)
    model = YOLO(model_path)
    boxes = model.predict(frame, verbose=False)[0].boxes
    heights = [float(b[3] - b[1]) for b, c in zip(boxes.xyxy.tolist(), boxes.cls.tolist(), strict=True)
               if model.names[int(c)] == class_name]
    if not heights:
        raise ValueError(f"No '{class_name}' found in {image_path}")
    return max(heights)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    m = sub.add_parser("measure", help="from a photo / measurement at a known distance")
    m.add_argument("--distance", type=float, required=True, help="metres from the camera")
    m.add_argument("--real-height", type=float, required=True, help="object height in metres")
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--pixel-height", type=float, help="object height in the image (pixels)")
    g.add_argument("--image", help="photo; YOLO measures the object for you")
    m.add_argument("--class", dest="cls", default="person", help="object class in the photo")
    m.add_argument("--model", default="yolo11n.pt")
    s = sub.add_parser("spec", help="from the camera datasheet")
    s.add_argument("--camera", choices=sorted(CAMERAS))
    s.add_argument("--focal-mm", type=float)
    s.add_argument("--sensor-width-mm", type=float)
    s.add_argument("--width", type=int, required=True, help="capture width in pixels, e.g. 640")
    a = p.parse_args(argv)

    if a.mode == "measure":
        h = a.pixel_height or measure_box_height(a.image, a.cls, a.model)
        focal = focal_from_measurement(h, a.distance, a.real_height)
        print(f"Object height: {h:.1f} px")
    else:
        focal_mm, sensor_mm = CAMERAS[a.camera] if a.camera else (a.focal_mm, a.sensor_width_mm)
        if not focal_mm or not sensor_mm:
            p.error("give --camera, or both --focal-mm and --sensor-width-mm")
        focal = focal_from_specs(focal_mm, sensor_mm, a.width)
    print(f"Focal length: {focal:.1f} px\n\nAdd to your config:\nzone:\n  focal_length_px: {focal:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
