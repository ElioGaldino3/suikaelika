"""Generic SDL joystick adapter with configurable, profile-friendly bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from suika_elika.contracts.input import InputAction

from .manager import InputSample


@dataclass(frozen=True, slots=True)
class JoystickBindings:
    """Physical indices for a generic device; buttons are never guessed."""

    horizontal_axis: int | None = 0
    vertical_axis: int | None = 1
    dpad_hat: int | None = 0
    fine_adjust_button: int | None = None
    button_actions: Mapping[int, tuple[InputAction, ...]] | None = None

    def __post_init__(self) -> None:
        for name in ("horizontal_axis", "vertical_axis", "dpad_hat", "fine_adjust_button"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative index or None")
        actions = self.button_actions or {}
        if any(type(button) is not int or button < 0 for button in actions):
            raise ValueError("button action keys must be non-negative integer indices")
        for button_actions in actions.values():
            if not isinstance(button_actions, tuple) or any(
                not isinstance(action, InputAction) for action in button_actions
            ):
                raise TypeError("button actions must be tuples of InputAction values")


class JoystickAdapter:
    """Translate one generic joystick into normalized semantic input samples.

    The adapter deliberately ships with no button-to-action mapping: generic
    joystick button numbers are not standardized. A profile or remapping flow
    must supply ``button_actions`` before face buttons cause gameplay actions.
    """

    def __init__(
        self,
        joystick: Any,
        *,
        device_index: int,
        bindings: JoystickBindings | None = None,
    ) -> None:
        if type(device_index) is not int or device_index < 0:
            raise ValueError("device_index must be a non-negative integer")
        self.joystick = joystick
        self.device_index = device_index
        self.bindings = bindings or JoystickBindings()
        self.instance_id = int(joystick.get_instance_id())
        self.name = self._metadata("get_name", "Generic joystick")
        self.guid = self._metadata("get_guid", "")
        self._button_states: dict[int, bool] = {}
        self._closed = False

    def poll(self) -> InputSample:
        """Read current state; action edges are emitted only on button rises."""
        if self._closed:
            return InputSample()

        axis_x = self._axis(self.bindings.horizontal_axis)
        axis_y = self._axis(self.bindings.vertical_axis)
        left = right = up = down = False
        hat_index = self.bindings.dpad_hat
        if hat_index is not None and hat_index < self._count("get_numhats"):
            hat_x, hat_y = self.joystick.get_hat(hat_index)
            left, right = hat_x < 0, hat_x > 0
            up, down = hat_y > 0, hat_y < 0

        pressed = self._button(self.bindings.fine_adjust_button)
        edges: list[InputAction] = []
        for button, actions in (self.bindings.button_actions or {}).items():
            is_down = self._button(button)
            was_down = self._button_states.get(button, False)
            if is_down and not was_down:
                edges.extend(actions)
            self._button_states[button] = is_down

        return InputSample(
            analog_x=axis_x,
            analog_y=axis_y,
            left=left,
            right=right,
            up=up,
            down=down,
            fine_adjust=pressed,
            action_edges=tuple(edges),
        )

    def reset_edges(self) -> None:
        """Forget held buttons after a remap or a focus/device lifecycle change."""
        self._button_states.clear()

    def rumble(self, low_frequency: float, high_frequency: float, duration_ms: int) -> bool:
        """Try optional rumble and report unsupported/failed devices as False."""
        rumble = getattr(self.joystick, "rumble", None)
        if not callable(rumble):
            return False
        try:
            return bool(rumble(low_frequency, high_frequency, duration_ms))
        except Exception:
            return False

    def close(self) -> None:
        """Release the handle if the SDL wrapper supports an explicit quit."""
        if self._closed:
            return
        self._closed = True
        quit_device = getattr(self.joystick, "quit", None)
        if callable(quit_device):
            quit_device()

    def _axis(self, index: int | None) -> float:
        if index is None or index >= self._count("get_numaxes"):
            return 0.0
        value = float(self.joystick.get_axis(index))
        if not isfinite(value):
            return 0.0
        # SDL joystick axes already use floats in [-1, 1]. Clamp small driver
        # excursions so InputSample retains its normalized contract.
        return max(-1.0, min(1.0, value))

    def _button(self, index: int | None) -> bool:
        return (
            index is not None
            and index < self._count("get_numbuttons")
            and bool(self.joystick.get_button(index))
        )

    def _count(self, getter: str) -> int:
        method = getattr(self.joystick, getter, None)
        return int(method()) if callable(method) else 0

    def _metadata(self, getter: str, fallback: str) -> str:
        method = getattr(self.joystick, getter, None)
        if not callable(method):
            return fallback
        try:
            return str(method())
        except Exception:
            return fallback
