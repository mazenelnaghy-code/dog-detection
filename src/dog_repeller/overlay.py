"""Draw the danger zone, dog boxes, centre dots and a status banner on a frame."""

from __future__ import annotations

import cv2
import numpy as np

from .domain import Threat

GREEN, YELLOW, RED, WHITE, DARK = (80, 200, 80), (0, 210, 255), (40, 40, 230), (255, 255, 255), (30, 30, 30)
LEVEL_COLORS = {"CLEAR": GREEN, "DETECTED": YELLOW, "DANGER": RED}
FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_H = 30


def draw_overlay(frame: np.ndarray, zone_rect: tuple[int, int, int, int],
                 threats: list[Threat], status: dict) -> np.ndarray:
    """Draw in place and return the frame."""
    danger = any(t.dangerous for t in threats)
    x1, y1, x2, y2 = zone_rect
    if danger:  # tint the zone red
        roi = frame[y1:y2, x1:x2]
        roi[:] = cv2.addWeighted(roi, 0.7, np.full_like(roi, RED), 0.3, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), RED if danger else YELLOW, 2)
    cv2.putText(frame, "DANGER ZONE", (x1 + 6, y1 + 20), FONT, 0.55, RED if danger else YELLOW, 2)

    for t in threats:
        color = RED if t.dangerous else GREEN
        bx1, by1, bx2, by2 = (int(v) for v in t.detection.box)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)
        cv2.circle(frame, (int(t.center[0]), int(t.center[1])), 6, color, -1)
        label = f"dog {t.detection.conf:.2f}"
        if t.distance_m is not None:
            label += f"  {t.distance_m:.1f} m"
        (_, th), _ = cv2.getTextSize(label, FONT, 0.55, 2)
        above = by1 - th - 12 > BANNER_H  # keep the label clear of the status banner
        _label(frame, label, (bx1, by1 - 6 if above else max(by1, BANNER_H) + th + 8), color)

    _banner(frame, status)
    return frame


def _label(frame: np.ndarray, text: str, org: tuple[int, int], color) -> None:
    (w, h), _ = cv2.getTextSize(text, FONT, 0.55, 2)
    x, y = org
    cv2.rectangle(frame, (x, y - h - 6), (x + w + 6, y + 4), color, -1)
    cv2.putText(frame, text, (x + 3, y - 2), FONT, 0.55, DARK, 2)


def _banner(frame: np.ndarray, status: dict) -> None:
    level = status.get("level", "CLEAR")
    cv2.rectangle(frame, (0, 0), (frame.shape[1], BANNER_H), DARK, -1)
    left = f"{level} | {status.get('state', '').upper()}"
    if status.get("seconds_left"):
        left += f" {status['seconds_left']:.0f}s"
    cv2.putText(frame, left, (8, 21), FONT, 0.6, LEVEL_COLORS.get(level, WHITE), 2)
    right = (f"{'ARMED' if status.get('armed') else 'DISARMED'} | "
             f"repels {status.get('total_bursts', 0)} | {status.get('fps', 0):.1f} fps")
    (w, _), _ = cv2.getTextSize(right, FONT, 0.5, 1)
    cv2.putText(frame, right, (frame.shape[1] - w - 8, 20), FONT, 0.5, WHITE, 1)
