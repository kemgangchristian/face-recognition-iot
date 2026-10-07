"""
Tests de l'actionneur de porte — périphérique GPIO et minuteur simulés,
aucun matériel nécessaire. Vérifie surtout le comportement FAIL-CLOSED.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from access.door_actuator import (
    GpioRelayActuator,
    NullDoorActuator,
    build_actuator_from_env,
)


class FakeDevice:
    def __init__(self, fail_on=False, fail_off=False):
        self.is_on = False
        self.closed = False
        self.fail_on = fail_on
        self.fail_off = fail_off
        self.history = []

    def on(self):
        if self.fail_on:
            raise OSError("relais HS")
        self.is_on = True
        self.history.append("on")

    def off(self):
        if self.fail_off:
            raise OSError("off HS")
        self.is_on = False
        self.history.append("off")

    def close(self):
        self.closed = True


class FakeTimer:
    """Minuteur manuel : ne tire jamais tout seul, on le déclenche à la main."""
    instances = []

    def __init__(self, interval, function):
        self.interval, self.function = interval, function
        self.cancelled = False
        self.daemon = False
        FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.function()


def make(device=None, **kwargs):
    FakeTimer.instances = []
    device = device or FakeDevice()
    actuator = GpioRelayActuator(
        pin=17, unlock_seconds=5.0,
        device_factory=lambda pin, active_high: device,
        timer_factory=FakeTimer, **kwargs,
    )
    return actuator, device


def test_relay_starts_locked():
    _, device = make()
    assert device.is_on is False
    assert device.history == ["off"]


def test_unlock_opens_then_relocks_when_the_timer_fires():
    actuator, device = make()
    actuator.unlock("Christian")
    assert device.is_on is True
    assert FakeTimer.instances[-1].interval == 5.0
    FakeTimer.instances[-1].fire()
    assert device.is_on is False


def test_second_unlock_extends_instead_of_stacking_timers():
    actuator, device = make()
    actuator.unlock("A")
    first_timer = FakeTimer.instances[-1]
    actuator.unlock("B")
    assert first_timer.cancelled is True          # l'ancienne temporisation est annulée
    first_timer.fire()                            # elle ne reverrouille donc pas
    assert device.is_on is True
    FakeTimer.instances[-1].fire()
    assert device.is_on is False


def test_failure_to_open_leaves_the_door_locked():
    actuator, device = make(FakeDevice(fail_on=True))
    actuator.unlock("Christian")                  # ne doit pas lever d'exception
    assert device.is_on is False
    assert FakeTimer.instances == []              # pas de minuteur armé pour rien


def test_close_locks_and_releases_the_hardware():
    actuator, device = make()
    actuator.unlock("Christian")
    actuator.close()
    assert device.is_on is False and device.closed is True
    assert FakeTimer.instances[-1].cancelled is True


def test_close_survives_a_relay_that_cannot_turn_off():
    actuator, device = make()
    device.fail_off = True
    actuator.close()                              # ne doit pas lever


def test_null_actuator_counts_but_opens_nothing():
    actuator = NullDoorActuator()
    actuator.unlock("Christian")
    actuator.lock()
    assert actuator.unlock_count == 1


def test_env_without_pin_gives_the_null_actuator():
    assert isinstance(build_actuator_from_env({}), NullDoorActuator)


def test_env_with_unusable_gpio_falls_back_to_the_null_actuator():
    # gpiozero absent (CI) ou broche invalide : jamais d'exception, porte verrouillée.
    actuator = build_actuator_from_env({"DOOR_RELAY_GPIO_PIN": "not-a-pin"})
    assert isinstance(actuator, NullDoorActuator)
    