"""Output devices: the audible buzzer and the relay that powers the ultrasonic repeller.

Two pin backends share one tiny interface (on / off / blink / close / is_active):

* ``SimPin``  - prints state changes; used on a PC or when no hardware is connected.
* ``GpioPin`` - a real Raspberry Pi pin through gpiozero (works on Pi 4 and Pi 5).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from .config import BuzzerConfig, Config

log = logging.getLogger(__name__)


class SimPin:
    def __init__(self, name: str):
        self.name = name
        self.is_active = False
        self.blinks: list[tuple[float, float, int]] = []

    def on(self) -> None:
        if not self.is_active:
            self.is_active = True
            log.warning("[SIM] %s -> ON", self.name)

    def off(self) -> None:
        if self.is_active:
            self.is_active = False
            log.warning("[SIM] %s -> OFF", self.name)

    def blink(self, on_s: float, off_s: float, n: int) -> None:
        self.blinks.append((on_s, off_s, n))
        log.warning("[SIM] %s -> beep x%d", self.name, n)

    def close(self) -> None:
        self.off()


class GpioPin:
    def __init__(self, pin: int, active_high: bool):
        from gpiozero import DigitalOutputDevice  # only available on the Pi

        self._dev = DigitalOutputDevice(pin, active_high=active_high, initial_value=False)

    @property
    def is_active(self) -> bool:
        return bool(self._dev.value)

    def on(self) -> None:
        self._dev.on()

    def off(self) -> None:
        self._dev.off()

    def blink(self, on_s: float, off_s: float, n: int) -> None:
        self._dev.blink(on_time=on_s, off_time=off_s, n=n, background=True)

    def close(self) -> None:
        self._dev.off()
        self._dev.close()


class Repeller:
    """Relay that switches the 12 V ultrasonic repeller module."""

    def __init__(self, pin: SimPin | GpioPin):
        self.pin = pin

    @property
    def is_on(self) -> bool:
        return self.pin.is_active

    def set(self, on: bool) -> None:
        if on != self.pin.is_active:
            self.pin.on() if on else self.pin.off()

    def close(self) -> None:
        self.pin.close()


class Buzzer:
    """Audible buzzer that tells people a dog was detected."""

    def __init__(self, pin: SimPin | GpioPin, cfg: BuzzerConfig):
        self.pin = pin
        self.cfg = cfg

    def beep(self) -> None:
        self.pin.blink(self.cfg.on_s, self.cfg.off_s, self.cfg.beeps)

    def close(self) -> None:
        self.pin.close()


class Watchdog:
    """Forces the repeller OFF if the main loop stops calling ``feed()`` while it is ON.

    Normally the controller switches the repeller off after ``burst_s``. If the program ever
    freezes mid-burst (driver hang, stuck camera ...) this thread still cuts the power.
    """

    def __init__(self, repeller: Repeller, timeout_s: float,
                 clock: Callable[[], float] = time.monotonic, interval_s: float = 0.25):
        self.repeller, self.timeout_s, self.clock, self.interval_s = repeller, timeout_s, clock, interval_s
        self._last_feed = clock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def feed(self) -> None:
        self._last_feed = self.clock()

    def check(self) -> bool:
        """One watchdog tick. Returns True if it had to switch the repeller off."""
        if self.repeller.is_on and self.clock() - self._last_feed > self.timeout_s:
            self.repeller.pin.off()
            log.error("Main loop frozen for %.1f s - watchdog switched the repeller OFF",
                      self.clock() - self._last_feed)
            return True
        return False

    def start(self) -> None:
        if self.timeout_s > 0 and self._thread is None:
            self._thread = threading.Thread(target=self._run, name="repeller-watchdog", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.check()


def create_outputs(cfg: Config) -> tuple[Buzzer, Repeller]:
    if cfg.hardware.backend == "gpio":
        buzzer_pin = GpioPin(cfg.buzzer.pin, cfg.buzzer.active_high)
        repeller_pin = GpioPin(cfg.repeller.pin, cfg.repeller.active_high)
    else:
        buzzer_pin, repeller_pin = SimPin("BUZZER"), SimPin("ULTRASONIC REPELLER")
    return Buzzer(buzzer_pin, cfg.buzzer), Repeller(repeller_pin)
