"""Danger-zone geometry and camera-based distance estimation (pure functions, no I/O).

The original project put a dot at the centre of every dog's bounding box and declared danger
when that dot entered a zone drawn on the screen. Instead of a distance sensor it used the
camera itself: with a pinhole camera model an object of real height H at distance D appears
``h = f * H / D`` pixels tall, so ``D = f * H / h`` once the focal length ``f`` (in pixels) is
known (see tools/calibrate_focal.py).
"""

from __future__ import annotations

from collections.abc import Iterable

from .config import ZoneConfig
from .domain import Box, Detection, Threat, ThreatLevel


def box_center(box: Box) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def estimate_distance(box_height_px: float, focal_length_px: float | None,
                      real_height_m: float) -> float | None:
    if not focal_length_px or box_height_px <= 0:
        return None
    return focal_length_px * real_height_m / box_height_px


class DangerZone:
    def __init__(self, cfg: ZoneConfig):
        self.cfg = cfg

    def pixel_rect(self, width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = self.cfg.rect
        return (round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height))

    def assess(self, detections: Iterable[Detection], width: int, height: int) -> list[Threat]:
        zx1, zy1, zx2, zy2 = self.pixel_rect(width, height)
        threats = []
        for d in detections:
            cx, cy = box_center(d.box)
            in_zone = zx1 <= cx <= zx2 and zy1 <= cy <= zy2
            distance = estimate_distance(d.box[3] - d.box[1], self.cfg.focal_length_px,
                                         self.cfg.dog_height_m)
            close = distance is not None and distance <= self.cfg.danger_distance_m
            threats.append(Threat(d, (cx, cy), in_zone, distance, self._dangerous(in_zone, close)))
        return threats

    def _dangerous(self, in_zone: bool, close: bool) -> bool:
        rule = self.cfg.rule
        if rule == "zone":
            return in_zone
        if rule == "distance":
            return close
        if rule == "both":
            return in_zone and close
        return in_zone or close  # "either"


def frame_level(threats: Iterable[Threat]) -> ThreatLevel:
    level = ThreatLevel.CLEAR
    for t in threats:
        level = max(level, ThreatLevel.DANGER if t.dangerous else ThreatLevel.DETECTED)
    return level
