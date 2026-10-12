"""Typed configuration loaded from YAML files.

A YAML file may start with ``base: other.yaml`` (path relative to the file) to inherit every
setting it does not override. Unknown keys are rejected so typos never pass silently.
"""

from __future__ import annotations

import copy
import dataclasses
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DOG_LOOKALIKES = ("bear", "cow", "sheep", "horse", "zebra", "elephant", "giraffe")


@dataclass
class CameraConfig:
    source: str = "0"  # "picamera", webcam index ("0"), video file path or stream URL
    width: int = 640
    height: int = 480
    fps: int = 30
    loop: bool = False  # restart video files when they end
    realtime: bool = False  # play video files at real speed, skipping frames like a live camera
    rotate: int = 0  # 0, 90, 180 or 270 degrees (for upside-down mounting)


@dataclass
class ModelConfig:
    path: str = "yolo11n.pt"  # .pt, NCNN folder (*_ncnn_model) or .onnx
    imgsz: int = 640
    conf: float = 0.25
    iou: float = 0.5
    device: str = "cpu"
    class_name: str = "dog"
    compete: bool = True  # let cat/person/... classes suppress look-alike dog boxes
    # COCO often labels Egyptian street dogs as one of these; count them as dogs too.
    # (Never "cat" or "person" - children must not trigger the repeller.)
    also_count: list[str] = field(default_factory=lambda: list(DOG_LOOKALIKES))
    min_box_area: float = 0.002  # fraction of the frame; ignores tiny, far-away boxes


@dataclass
class ZoneConfig:
    rect: list[float] = field(default_factory=lambda: [0.2, 0.4, 0.8, 1.0])  # x1 y1 x2 y2, 0..1
    rule: str = "either"  # zone | distance | either | both
    focal_length_px: float | None = None  # from tools/calibrate_focal.py; None disables distance
    dog_height_m: float = 0.5  # average shoulder height of the dogs you expect
    danger_distance_m: float = 3.0


@dataclass
class ControllerConfig:
    window_frames: int = 6  # sliding window used to confirm a detection
    confirm_frames: int = 3  # frames inside the window that must agree
    burst_s: float = 5.0  # repeller ON time per burst
    cooldown_s: float = 3.0  # repeller OFF time between bursts
    max_bursts: int = 6  # consecutive bursts before a forced rest
    lockout_s: float = 60.0  # forced rest (protects the device, reduces habituation)
    start_armed: bool = True


@dataclass
class BuzzerConfig:
    mode: str = "detect"  # detect: any dog | danger: only close dogs | off
    pin: int = 27
    active_high: bool = True
    beeps: int = 2
    on_s: float = 0.15
    off_s: float = 0.1
    min_interval_s: float = 5.0


@dataclass
class RepellerConfig:
    pin: int = 17
    active_high: bool = False  # most 5 V relay boards switch ON when the input is LOW
    watchdog_s: float = 5.0  # force OFF if the program freezes this long (0 = disabled)


@dataclass
class HardwareConfig:
    backend: str = "sim"  # sim (print to console) | gpio (real Raspberry Pi pins)


@dataclass
class DisplayConfig:
    window: bool = True
    fullscreen: bool = False
    title: str = "Dog Repeller"


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"  # use 0.0.0.0 to reach it from a phone on the same Wi-Fi
    port: int = 8000
    token: str = ""  # if set, arm/disarm/test require ?token=... or the X-Token header
    jpeg_quality: int = 70


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    zone: ZoneConfig = field(default_factory=ZoneConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    buzzer: BuzzerConfig = field(default_factory=BuzzerConfig)
    repeller: RepellerConfig = field(default_factory=RepellerConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    log_level: str = "INFO"


def load_config(path: str | Path | None = None) -> Config:
    data = _read_yaml(Path(path)) if path else {}
    cfg = _build(Config, data, "")
    _validate(cfg)
    return cfg


def apply_overrides(cfg: Config, overrides: dict[str, Any]) -> Config:
    """Return a new Config with dotted keys (e.g. ``"camera.source"``) replaced."""
    data = dataclasses.asdict(cfg)
    for dotted, value in overrides.items():
        node = data
        *parents, leaf = dotted.split(".")
        for part in parents:
            if not isinstance(node.get(part), dict):
                raise ValueError(f"Unknown config key: {dotted}")
            node = node[part]
        if leaf not in node:
            raise ValueError(f"Unknown config key: {dotted}")
        node[leaf] = value
    new = _build(Config, data, "")
    _validate(new)
    return new


def _read_yaml(path: Path, _seen: frozenset[Path] = frozenset()) -> dict:
    path = path.resolve()
    if path in _seen:
        raise ValueError(f"Circular 'base:' reference in {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    base = data.pop("base", None)
    if base:
        return _deep_merge(_read_yaml(path.parent / base, _seen | {path}), data)
    return data


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _build(cls: type, data: dict, prefix: str) -> Any:
    hints = typing.get_type_hints(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    for key in data:
        if key not in names:
            raise ValueError(f"Unknown config key: {prefix}{key}")
    kwargs = {}
    for name, value in data.items():
        hint = hints[name]
        if dataclasses.is_dataclass(hint):
            if not isinstance(value, dict):
                raise ValueError(f"Config section '{prefix}{name}' must be a mapping")
            kwargs[name] = _build(hint, value, f"{prefix}{name}.")
        else:
            kwargs[name] = _coerce(value, hint, f"{prefix}{name}")
    return cls(**kwargs)


def _coerce(value: Any, hint: Any, key: str) -> Any:
    if value is None:
        return None
    if hint is str:
        return str(value)
    if hint is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return value
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        return value
    if hint is float or hint == (float | None):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        return float(value)
    if typing.get_origin(hint) is list:
        item = typing.get_args(hint)[0]
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        return [str(v) if item is str else float(v) for v in value]
    return value


def _validate(cfg: Config) -> None:
    rect = cfg.zone.rect
    if len(rect) != 4 or not all(0.0 <= v <= 1.0 for v in rect):
        raise ValueError("zone.rect must be 4 numbers between 0 and 1")
    if not (rect[0] < rect[2] and rect[1] < rect[3]):
        raise ValueError("zone.rect must be [x1, y1, x2, y2] with x1 < x2 and y1 < y2")
    if {"cat", "person"} & {c.lower() for c in cfg.model.also_count}:
        raise ValueError("model.also_count must not contain 'cat' or 'person'")
    _choice("zone.rule", cfg.zone.rule, {"zone", "distance", "either", "both"})
    _choice("buzzer.mode", cfg.buzzer.mode, {"detect", "danger", "off"})
    _choice("hardware.backend", cfg.hardware.backend, {"sim", "gpio"})
    _choice("camera.rotate", cfg.camera.rotate, {0, 90, 180, 270})
    c = cfg.controller
    if not 1 <= c.confirm_frames <= c.window_frames:
        raise ValueError("controller.confirm_frames must be between 1 and window_frames")
    if c.burst_s <= 0 or c.cooldown_s < 0 or c.lockout_s < 0 or c.max_bursts < 1:
        raise ValueError("controller timings must be positive")
    if cfg.repeller.watchdog_s < 0:
        raise ValueError("repeller.watchdog_s must be >= 0")
    if not 0.0 < cfg.model.conf < 1.0:
        raise ValueError("model.conf must be between 0 and 1")


def _choice(key: str, value: Any, allowed: set) -> None:
    if value not in allowed:
        raise ValueError(f"{key} must be one of {sorted(allowed)}, got {value!r}")
