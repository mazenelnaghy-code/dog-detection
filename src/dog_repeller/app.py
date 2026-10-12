"""Main loop: camera -> YOLO -> danger zone -> controller -> buzzer / repeller / screen / web.

Run ``python -m dog_repeller --help`` for options. Keyboard (when the window is open):
``q``/``Esc`` quit, ``a`` arm, ``d`` disarm, ``t`` test the repeller.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from .config import Config, apply_overrides, load_config
from .controller import Controller, State
from .dashboard import DashboardState, start_dashboard
from .domain import Detection
from .hardware import Buzzer, Repeller, Watchdog, create_outputs
from .overlay import draw_overlay
from .sources import FrameSource, open_source
from .zone import DangerZone, frame_level

log = logging.getLogger("dog_repeller")


class CameraLost(RuntimeError):
    """A live camera stopped delivering frames (the service manager should restart us)."""
DEFAULT_CONFIG = Path("config/default.yaml")


class App:
    def __init__(self, cfg: Config, detector: Any, source: FrameSource, buzzer: Buzzer,
                 repeller: Repeller, dashboard: DashboardState | None = None,
                 clock: Callable[[], float] = time.monotonic, record: Path | None = None):
        self.cfg, self.detector, self.source = cfg, detector, source
        self.buzzer, self.repeller, self.dashboard, self.clock = buzzer, repeller, dashboard, clock
        self.zone = DangerZone(cfg.zone)
        self.controller = Controller(cfg.controller, cfg.buzzer)
        self.fps = 0.0
        self.last_frame: np.ndarray | None = None
        self._last_t: float | None = None
        self._window = False
        self._quit = False
        self._server = None
        self._record_path, self._writer = record, None
        self.watchdog = Watchdog(repeller, cfg.repeller.watchdog_s)
        self.repeller.set(False)  # fail-safe start

    def step(self) -> bool:
        """Process one frame. Returns False when the source has ended or the user quit."""
        frame = self.source.read()
        if frame is None:
            return False
        now = self.clock()
        self._update_fps(now)
        self._apply_commands(self.dashboard.pop_commands() if self.dashboard else [])

        detections: list[Detection] = self.detector.detect(frame)
        h, w = frame.shape[:2]
        threats = self.zone.assess(detections, w, h)
        before = self.controller.state
        commands = self.controller.update(frame_level(threats), now)
        try:
            self.repeller.set(commands.repeller_on)
            if commands.beep:
                self.buzzer.beep()
        except Exception:
            self.repeller.set(False)
            raise
        self.watchdog.feed()
        self._log_transition(before, len(detections))

        status = self.status(now, len(detections))
        watched = self.dashboard is not None and self.dashboard.viewers > 0
        if self.cfg.display.window or watched or self._record_path:
            frame = draw_overlay(frame, self.zone.pixel_rect(w, h), threats, status)
        self.last_frame = frame
        if self._record_path:
            self._record(frame)
        if self.dashboard:
            jpeg = None
            if watched:  # JPEG-encode only while someone is watching the stream
                ok, buf = cv2.imencode(".jpg", frame,
                                       [cv2.IMWRITE_JPEG_QUALITY, self.cfg.dashboard.jpeg_quality])
                jpeg = buf.tobytes() if ok else None
            self.dashboard.update(jpeg, status)
        return self._show(frame) if self.cfg.display.window else True

    def status(self, now: float, dogs: int) -> dict:
        return {**self.controller.snapshot(now), "dogs": dogs, "fps": round(self.fps, 1),
                "repeller_on": self.repeller.is_on}

    def run(self) -> None:
        """Run until the source ends. Raises CameraLost if a live camera stops delivering."""
        if self.dashboard and self.cfg.dashboard.enabled:
            try:
                self._server = start_dashboard(self.dashboard, self.cfg.dashboard)
            except OSError as e:  # e.g. port in use - keep protecting, just without the web page
                log.error("Dashboard could not start (%s); continuing without it", e)
        log.info("Running - source=%s, hardware=%s, armed=%s", self.cfg.camera.source,
                 self.cfg.hardware.backend, self.controller.armed)
        self.watchdog.feed()
        self.watchdog.start()
        try:
            while self.step():
                pass
            if self.source.is_live and not self._quit:
                raise CameraLost("camera stopped delivering frames")
        finally:
            self.close()

    def close(self) -> None:
        self.watchdog.stop()
        self.repeller.set(False)
        for closer in (self.repeller.close, self.buzzer.close, self.source.close):
            try:
                closer()
            except Exception:
                log.exception("Error while closing")
        if self._writer:
            self._writer.release()
            log.info("Recording saved to %s", self._record_path)
        if self._window:
            cv2.destroyAllWindows()
        if self._server:
            self._server.shutdown()
        log.info("Stopped. Repeller OFF. Total repels: %d", self.controller.total_bursts)

    # ---- helpers ------------------------------------------------------------------------
    def _record(self, frame: np.ndarray) -> None:
        """Write at a fixed fps, repeating frames so the recording plays in real time."""
        fps, now = self.cfg.camera.fps, self.clock()
        if self._writer is None:
            fourcc = cv2.VideoWriter_fourcc(*("mp4v" if self._record_path.suffix == ".mp4" else "MJPG"))
            self._writer = cv2.VideoWriter(str(self._record_path), fourcc, fps,
                                           (frame.shape[1], frame.shape[0]))
            self._rec_start, self._rec_frames = now, 0
        due = max(self._rec_frames + 1, int((now - self._rec_start) * fps) + 1)
        while self._rec_frames < due:
            self._writer.write(frame)
            self._rec_frames += 1

    def _apply_commands(self, commands: list[str]) -> None:
        for cmd in commands:
            {"arm": self.controller.arm, "disarm": self.controller.disarm,
             "test": self.controller.request_test}[cmd]()
            log.info("Command: %s", cmd)

    def _update_fps(self, now: float) -> None:
        if self._last_t is not None and now > self._last_t:
            inst = 1.0 / (now - self._last_t)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
        self._last_t = now

    def _log_transition(self, before: State, dogs: int) -> None:
        after = self.controller.state
        if after is before:
            return
        if after is State.REPELLING and self.controller.testing:
            log.warning("Manual test -> ULTRASONIC REPELLER ON for %.0f s",
                        self.cfg.controller.burst_s)
        elif after is State.REPELLING:
            log.warning("Dog in danger zone (%d visible) -> ULTRASONIC REPELLER ON (burst %d)",
                        dogs, self.controller.bursts)
        elif after is State.LOCKOUT:
            log.warning("Max bursts reached -> resting for %.0f s", self.cfg.controller.lockout_s)
        else:
            log.info("State: %s -> %s", before.value, after.value)

    def _show(self, frame: np.ndarray) -> bool:
        title = self.cfg.display.title
        if not self._window:
            cv2.namedWindow(title, cv2.WINDOW_NORMAL)
            if self.cfg.display.fullscreen:
                cv2.setWindowProperty(title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            self._window = True
        cv2.imshow(title, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            self._quit = True
            return False
        self._apply_commands({ord("a"): ["arm"], ord("d"): ["disarm"],
                              ord("t"): ["test"]}.get(key, []))
        return True


# ---- command line ------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dog_repeller", description="AI dog detection & repeller")
    p.add_argument("--config", type=Path, help="YAML config (default: config/default.yaml)")
    p.add_argument("--source", help='"0" webcam, "picamera", video/image file, folder or URL')
    p.add_argument("--model", help="model path (.pt, *_ncnn_model folder or .onnx)")
    p.add_argument("--sim", action="store_true", help="simulate GPIO (no real hardware)")
    p.add_argument("--no-window", action="store_true", help="do not open a video window")
    p.add_argument("--no-dashboard", action="store_true", help="do not start the web dashboard")
    p.add_argument("--loop", action="store_true", help="replay a video file forever")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override any config value, e.g. --set zone.rule=zone (repeatable)")
    p.add_argument("--log-level", help="DEBUG, INFO, WARNING ...")
    p.add_argument("--demo", action="store_true",
                   help="built-in demo with sample photos (no camera or hardware needed)")
    p.add_argument("--record", type=Path, metavar="FILE",
                   help="save the annotated video (.mp4 or .avi) - mind privacy")
    return p


def config_from_args(args: argparse.Namespace) -> Config:
    path = args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)
    overrides: dict[str, Any] = {}
    if getattr(args, "demo", False):
        from .demo import build_demo_video, demo_overrides

        overrides.update(demo_overrides(build_demo_video()))
    for item in args.set:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"--set expects KEY=VALUE, got {item!r}")
        overrides[key.strip()] = yaml.safe_load(value)
    flags = {"camera.source": args.source, "model.path": args.model, "log_level": args.log_level}
    overrides.update({k: v for k, v in flags.items() if v is not None})
    if args.sim:
        overrides["hardware.backend"] = "sim"
    if args.no_window:
        overrides["display.window"] = False
    if args.no_dashboard:
        overrides["dashboard.enabled"] = False
    if args.loop:
        overrides["camera.loop"] = True
    return apply_overrides(load_config(path), overrides)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(args)
    except (ValueError, OSError) as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
    logging.basicConfig(level=cfg.log_level.upper(),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # systemd stop -> clean shutdown

    from .detector import DogDetector  # imports Ultralytics (slow), so only here

    buzzer, repeller = create_outputs(cfg)
    source = None
    try:
        source = open_source(cfg.camera)
        detector = DogDetector(cfg.model)
    except Exception as e:
        for closer in (repeller.close, buzzer.close, source.close if source else None):
            if closer:
                closer()
        log.error("Startup failed: %s", e)
        return 1
    dashboard = DashboardState() if cfg.dashboard.enabled else None
    try:
        App(cfg, detector, source, buzzer, repeller, dashboard, record=args.record).run()
    except KeyboardInterrupt:
        pass
    except CameraLost as e:
        log.error("%s - exiting so systemd restarts the service", e)
        return 3
    return 0
