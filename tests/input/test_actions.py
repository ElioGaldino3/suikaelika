from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from suika_elika.contracts.input import InputAction
from suika_elika.input.actions import (
    ANALOG_SPEED,
    DEFAULT_DEADZONE,
    DIGITAL_SPEED,
    FINE_SPEED,
    normalize_axis,
    select_horizontal_axis,
    select_vertical_axis,
)
from suika_elika.input.manager import InputBackend, InputManager, InputSample


def test_analog_deadzone_and_curve_match_project_parameters() -> None:
    assert DEFAULT_DEADZONE == 0.20
    assert normalize_axis(0.0) == 0.0
    assert normalize_axis(0.20) == 0.0
    assert normalize_axis(-0.20) == 0.0
    assert normalize_axis(1.0) == 1.0
    assert normalize_axis(-1.0) == -1.0
    expected = ((0.60 - 0.20) / (1.0 - 0.20)) ** 1.3
    assert normalize_axis(0.60) == pytest.approx(expected)
    assert normalize_axis(-0.60) == pytest.approx(-expected)


@pytest.mark.parametrize(
    ("value", "deadzone", "exponent"),
    [
        (math.nan, 0.2, 1.3),
        (1.01, 0.2, 1.3),
        (-1.01, 0.2, 1.3),
        (0.5, 1.0, 1.3),
        (0.5, 0.2, 0.0),
    ],
)
def test_axis_normalizer_rejects_invalid_parameters(
    value: float,
    deadzone: float,
    exponent: float,
) -> None:
    with pytest.raises(ValueError):
        normalize_axis(value, deadzone=deadzone, exponent=exponent)


def test_dpad_has_priority_and_opposite_directions_cancel() -> None:
    analog = 0.8
    move, velocity = select_horizontal_axis(analog, left=True)
    assert move == -1.0
    assert velocity == -DIGITAL_SPEED

    move, velocity = select_horizontal_axis(analog, left=True, right=True)
    assert move == 0.0
    assert velocity == 0.0

    move_y = select_vertical_axis(-0.9, up=True, down=True)
    assert move_y == 0.0
    assert select_vertical_axis(-0.9, down=True) == 1.0


def test_analog_and_fine_movement_keep_proportionality_and_speed_limits() -> None:
    analog_axis = 0.6
    move, velocity = select_horizontal_axis(analog_axis)
    assert move == normalize_axis(analog_axis)
    assert velocity == pytest.approx(move * ANALOG_SPEED)

    fine_move, fine_velocity = select_horizontal_axis(analog_axis, fine_adjust=True)
    assert fine_move == move
    assert fine_velocity == pytest.approx(move * FINE_SPEED)

    digital_move, digital_velocity = select_horizontal_axis(0.0, right=True)
    assert digital_move == 1.0
    assert digital_velocity == DIGITAL_SPEED
    _, fine_digital_velocity = select_horizontal_axis(0.0, right=True, fine_adjust=True)
    assert fine_digital_velocity == FINE_SPEED


@dataclass
class FakeAdapter:
    sample: InputSample
    calls: int = 0

    def poll(self) -> InputSample:
        self.calls += 1
        return self.sample


def test_manager_polls_only_selected_backend_and_exposes_semantic_actions() -> None:
    manager = InputManager()
    native = FakeAdapter(InputSample(right=True, action_edges=(InputAction.DROP,)))
    keyboard = FakeAdapter(InputSample(left=True, action_edges=(InputAction.CONFIRM,)))
    manager.register_adapter(InputBackend.NATIVE, native)
    manager.register_adapter(InputBackend.KEYBOARD_EMULATED, keyboard)

    empty_manager = InputManager()
    with pytest.raises(ValueError, match="no adapter registered"):
        empty_manager.select_backend(InputBackend.NATIVE)

    manager.select_backend(InputBackend.NATIVE)
    first = manager.poll(0.0)
    assert first.frame.move_x == 1.0
    assert first.horizontal_velocity == DIGITAL_SPEED
    assert tuple(edge.action for edge in first.frame.edges) == (InputAction.DROP,)
    assert first.frame.edges[0].sequence == 0
    assert native.calls == 1
    assert keyboard.calls == 0

    manager.select_backend(InputBackend.KEYBOARD_EMULATED)
    second = manager.poll(0.0)
    assert second.frame.move_x == -1.0
    assert tuple(edge.action for edge in second.frame.edges) == (InputAction.CONFIRM,)
    assert second.frame.edges[0].sequence == 1
    assert native.calls == 1
    assert keyboard.calls == 1

    manager.select_backend(None)
    disabled = manager.poll(0.0)
    assert disabled.frame.move_x == 0.0
    assert disabled.frame.edges == ()
    assert native.calls == 1
    assert keyboard.calls == 1


def test_manager_emits_action_edges_once_without_a_residual_queue() -> None:
    adapter = FakeAdapter(InputSample(action_edges=(InputAction.DROP,), drop_held=True))
    manager = InputManager()
    manager.register_adapter(InputBackend.NATIVE, adapter)
    manager.select_backend(InputBackend.NATIVE)

    first = manager.poll(0.0)
    adapter.sample = InputSample(drop_held=True)
    second = manager.poll(0.0)
    assert tuple(edge.action for edge in first.frame.edges) == (InputAction.DROP,)
    assert second.frame.edges == ()
    assert first.frame.drop_held and second.frame.drop_held
    adapter.sample = InputSample()
    assert not manager.poll(0.0).frame.drop_held
    assert first.frame.edges[0].sequence == 0


def test_menu_axis_uses_threshold_hysteresis_and_ui_clock_repeat() -> None:
    adapter = FakeAdapter(InputSample(analog_y=-0.55))
    manager = InputManager()
    manager.register_adapter(InputBackend.NATIVE, adapter)
    manager.select_backend(InputBackend.NATIVE)

    def actions(delta: float = 0.0) -> tuple[InputAction, ...]:
        return tuple(edge.action for edge in manager.poll(delta).frame.edges)

    assert actions() == (InputAction.NAV_UP,)
    adapter.sample = InputSample(analog_y=-0.40)
    assert actions(0.27) == ()  # hysteresis keeps the direction active
    assert actions(0.01) == (InputAction.NAV_UP,)
    assert actions(0.10) == ()
    assert actions(0.01) == (InputAction.NAV_UP,)

    adapter.sample = InputSample(analog_y=-0.349)
    assert actions(0.0) == ()  # below release threshold, so no residual repeat
    adapter.sample = InputSample(analog_y=-0.55)
    assert actions() == (InputAction.NAV_UP,)  # a fresh activation is immediate


def test_menu_reverses_immediately_and_dpad_overrides_analog_axis() -> None:
    adapter = FakeAdapter(InputSample(analog_y=-0.6, down=True))
    manager = InputManager()
    manager.register_adapter(InputBackend.NATIVE, adapter)
    manager.select_backend(InputBackend.NATIVE)

    result = manager.poll(0.0)
    assert result.frame.move_y == 1.0
    assert tuple(edge.action for edge in result.frame.edges) == (InputAction.NAV_DOWN,)

    adapter.sample = InputSample(analog_y=-0.8)
    result = manager.poll(0.0)
    assert tuple(edge.action for edge in result.frame.edges) == (InputAction.NAV_UP,)


def test_manager_rejects_invalid_ui_delta_and_navigation_edges_from_adapter() -> None:
    manager = InputManager()
    adapter = FakeAdapter(InputSample())
    manager.register_adapter(InputBackend.NATIVE, adapter)
    manager.select_backend(InputBackend.NATIVE)

    with pytest.raises(ValueError, match="UI delta"):
        manager.poll(-0.1)
    with pytest.raises(ValueError, match="navigation actions"):
        InputSample(action_edges=(InputAction.NAV_DOWN,))
