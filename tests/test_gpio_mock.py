"""Exercise the real gpiozero code path with gpiozero's mock pin factory (no Raspberry Pi needed).

Checks the *electrical* level on the pins, which is what the relay board actually sees.
"""

import time

import pytest

gpiozero = pytest.importorskip("gpiozero")
from gpiozero import Device  # noqa: E402
from gpiozero.pins.mock import MockFactory  # noqa: E402

from dog_repeller.config import apply_overrides, load_config  # noqa: E402
from dog_repeller.hardware import GpioPin, create_outputs  # noqa: E402


@pytest.fixture(autouse=True)
def mock_pins():
    Device.pin_factory = MockFactory()
    yield Device.pin_factory
    Device.pin_factory.reset()
    Device.pin_factory = None


def level(factory, pin):
    return factory.pin(pin).state  # 1 = 3.3 V, 0 = GND


def test_active_low_relay_levels(mock_pins):
    pin = GpioPin(17, active_high=False)
    assert level(mock_pins, 17) == 1 and not pin.is_active  # OFF = HIGH on active-low boards
    pin.on()
    assert level(mock_pins, 17) == 0 and pin.is_active  # ON = pulled LOW
    pin.close()


def test_close_leaves_relay_off(mock_pins):
    pin = GpioPin(17, active_high=False)
    pin.on()
    pin.off()
    assert level(mock_pins, 17) == 1
    pin.close()


def test_active_high_buzzer_blinks_then_stops(mock_pins):
    pin = GpioPin(27, active_high=True)
    assert level(mock_pins, 27) == 0
    pin.blink(0.02, 0.02, 2)
    seen_high = False
    deadline = time.time() + 2
    while time.time() < deadline and not (seen_high and level(mock_pins, 27) == 0):
        seen_high |= level(mock_pins, 27) == 1
        time.sleep(0.002)
    assert seen_high and level(mock_pins, 27) == 0
    pin.close()


def test_create_outputs_gpio_backend_uses_configured_pins(mock_pins):
    cfg = apply_overrides(load_config(None), {"hardware.backend": "gpio"})
    buzzer, repeller = create_outputs(cfg)
    repeller.set(True)
    assert level(mock_pins, 17) == 0  # relay energised
    repeller.close()
    buzzer.close()
