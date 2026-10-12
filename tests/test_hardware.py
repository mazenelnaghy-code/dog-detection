from dog_repeller.config import BuzzerConfig, load_config
from dog_repeller.hardware import Buzzer, Repeller, SimPin, create_outputs


def test_repeller_on_off_and_close():
    pin = SimPin("repeller")
    rep = Repeller(pin)
    rep.set(True)
    assert rep.is_on and pin.is_active
    rep.set(False)
    assert not rep.is_on
    rep.set(True)
    rep.close()
    assert not pin.is_active  # fail-safe: closing always switches the relay off


def test_buzzer_beep_uses_config():
    pin = SimPin("buzzer")
    Buzzer(pin, BuzzerConfig(beeps=3)).beep()
    assert pin.blinks == [(0.15, 0.1, 3)]


def test_create_outputs_sim_backend():
    buzzer, repeller = create_outputs(load_config(None))
    assert isinstance(buzzer.pin, SimPin) and isinstance(repeller.pin, SimPin)
    assert not repeller.is_on


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_watchdog_trips_only_when_loop_is_frozen_while_on():
    from dog_repeller.hardware import Watchdog

    clock, rep = FakeClock(), Repeller(SimPin("rep"))
    dog = Watchdog(rep, timeout_s=5.0, clock=clock)
    clock.t = 60.0
    assert not dog.check()  # repeller OFF: nothing to do, however long
    rep.set(True)
    dog.feed()
    clock.t = 64.0
    assert not dog.check() and rep.is_on  # still within the timeout
    clock.t = 65.5
    assert dog.check() and not rep.is_on  # frozen for 5.5 s -> forced OFF


def test_watchdog_thread_starts_and_stops():
    from dog_repeller.hardware import Watchdog

    rep = Repeller(SimPin("rep"))
    dog = Watchdog(rep, timeout_s=0.05, interval_s=0.01)
    dog.start()
    rep.set(True)
    import time
    deadline = time.time() + 2
    while rep.is_on and time.time() < deadline:
        time.sleep(0.01)
    dog.stop()
    assert not rep.is_on
