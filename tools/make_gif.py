"""Turn a recorded video (python -m dog_repeller --record run.avi) into a small GIF for docs.

    python -m dog_repeller --demo --no-window --no-dashboard --set camera.loop=false --record demo.avi
    python tools/make_gif.py demo.avi docs/images/demo.gif --width 480 --every 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
from PIL import Image


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("video", type=Path)
    p.add_argument("gif", type=Path)
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--every", type=int, default=2, help="keep every Nth frame")
    p.add_argument("--colors", type=int, default=96)
    a = p.parse_args(argv)

    cap = cv2.VideoCapture(str(a.video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    frames, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % a.every == 0:
            h = int(frame.shape[0] * a.width / frame.shape[1])
            rgb = cv2.cvtColor(cv2.resize(frame, (a.width, h), interpolation=cv2.INTER_AREA),
                               cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb).quantize(colors=a.colors, method=Image.MEDIANCUT))
        i += 1
    if not frames:
        print(f"No frames read from {a.video}", file=sys.stderr)
        return 1
    a.gif.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(a.gif, save_all=True, append_images=frames[1:], loop=0, optimize=True,
                   duration=int(1000 * a.every / fps))
    print(f"{a.gif}: {len(frames)} frames, {a.gif.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
