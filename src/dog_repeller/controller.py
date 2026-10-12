"""Decision logic: when to beep and when to switch the ultrasonic repeller on.

Pure state machine with an injected clock (``now``), so it is fully unit-tested without
hardware. States::

    IDLE --confirmed DANGER--> REPELLING --burst_s--> COOLDOWN --cooldown_s--> REPELLING ...
                                   |                       '--no danger--> IDLE
                                   '--max_bursts reached--> LOCKOUT --lockout_s--> IDLE

A level is "confirmed" when it appears in at least ``confirm_frames`` of the last
``window_frames`` frames, which removes single-frame false detections.
"""

from __future__ import annotations

import math
from collections import deque
from enum import Enum

from .config import BuzzerConfig, ControllerConfig
from .domain import Commands, ThreatLevel


class State(str, Enum):
    IDLE = "idle"
    REPELLING = "repelling"
    COOLDOWN = "cooldown"
    LOCKOUT = "lockout"


class Controller:
    def __init__(self, cfg: ControllerConfig, buzzer_cfg: BuzzerConfig):
        self.cfg = cfg
        self.buzzer_cfg = buzzer_cfg
        self.armed = cfg.start_armed
        self.state = State.IDLE
        self.confirmed = ThreatLevel.CLEAR
        self.bursts = 0  # consecutive bursts in the current episode
        self.total_bursts = 0  # real (non-test) bursts since start
        self._levels: deque[ThreatLevel] = deque(maxlen=cfg.window_frames)
        self._until = 0.0
        self._test_pending = False
        self._test_burst = False
        self._last_beep = -math.inf

    # ---- commands from the user / dashboard -------------------------------------------
    def arm(self) -> None:
        self.armed = True

    def disarm(self) -> None:
        self.armed = False
        if self.state is State.COOLDOWN or (self.state is State.REPELLING and not self._test_burst):
            self._to_idle()

    def request_test(self) -> None:
        self._test_pending = True

    @property
    def testing(self) -> bool:
        """True while a manual test burst (not a real dog) is running."""
        return self.state is State.REPELLING and self._test_burst

    # ---- per-frame update ----------------------------------------------------------------
    def update(self, level: ThreatLevel, now: float) -> Commands:
        self._levels.append(level)
        previous = self.confirmed
        self.confirmed = self._confirmed_level()
        beep = self._should_beep(previous, now)
        self._advance(now)
        return Commands(repeller_on=self.state is State.REPELLING, beep=beep)

    def snapshot(self, now: float) -> dict:
        timed = self.state is not State.IDLE
        return {
            "state": self.state.value,
            "armed": self.armed,
            "level": self.confirmed.name,
            "bursts": self.bursts,
            "total_bursts": self.total_bursts,
            "seconds_left": round(max(0.0, self._until - now), 1) if timed else 0.0,
        }

    # ---- internals -----------------------------------------------------------------------
    def _confirmed_level(self) -> ThreatLevel:
        for lvl in (ThreatLevel.DANGER, ThreatLevel.DETECTED):
            if sum(1 for seen in self._levels if seen >= lvl) >= self.cfg.confirm_frames:
                return lvl
        return ThreatLevel.CLEAR

    def _should_beep(self, previous: ThreatLevel, now: float) -> bool:
        mode = self.buzzer_cfg.mode
        if mode == "off" or not self.armed:
            return False
        threshold = ThreatLevel.DETECTED if mode == "detect" else ThreatLevel.DANGER
        rising = previous < threshold <= self.confirmed
        if rising and now - self._last_beep >= self.buzzer_cfg.min_interval_s:
            self._last_beep = now
            return True
        return False

    def _advance(self, now: float) -> None:
        if self._test_pending:
            self._test_pending = False
            if self.state is not State.LOCKOUT:
                self._start_burst(now, test=True)
                return

        danger = self.armed and self.confirmed is ThreatLevel.DANGER
        if self.state is State.IDLE:
            if danger:
                self._start_burst(now)
        elif self.state is State.REPELLING:
            if now >= self._until:
                if self._test_burst:
                    self._to_idle()
                elif self.bursts >= self.cfg.max_bursts:
                    self.state, self._until = State.LOCKOUT, now + self.cfg.lockout_s
                else:
                    self.state, self._until = State.COOLDOWN, now + self.cfg.cooldown_s
        elif self.state is State.COOLDOWN:
            if now >= self._until:
                if danger:
                    self._start_burst(now)
                else:
                    self._to_idle()
        elif self.state is State.LOCKOUT and now >= self._until:
            self._to_idle()

    def _start_burst(self, now: float, test: bool = False) -> None:
        self.state, self._until, self._test_burst = State.REPELLING, now + self.cfg.burst_s, test
        if not test:
            self.bursts += 1
            self.total_bursts += 1

    def _to_idle(self) -> None:
        self.state, self.bursts, self._test_burst = State.IDLE, 0, False
