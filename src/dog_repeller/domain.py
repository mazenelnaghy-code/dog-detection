"""Small value types shared by every module."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


@dataclass(frozen=True)
class Detection:
    box: Box
    conf: float


class ThreatLevel(IntEnum):
    CLEAR = 0
    DETECTED = 1  # a dog is visible
    DANGER = 2  # a dog is close / inside the danger zone


@dataclass(frozen=True)
class Threat:
    detection: Detection
    center: tuple[float, float]
    in_zone: bool
    distance_m: float | None
    dangerous: bool


@dataclass(frozen=True)
class Commands:
    repeller_on: bool
    beep: bool
