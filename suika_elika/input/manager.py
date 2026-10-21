"""Backend-neutral input manager with exclusive source selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from suika_elika.contracts.input import InputAction, InputEdge, InputFrame

from .actions import select_horizontal_axis, select_vertical_axis


class InputBackend(str, Enum):
    """Mutually exclusive modes for native controls and translated keyboards."""

    NATIVE = "native"
    KEYBOARD_EMULATED = "keyboard_emulated"


@dataclass(frozen=True, slots=True)
class InputSample:
    """One poll from an adapter after device-specific values are normalized."""

    analog_x: float = 0.0
    analog_y: float = 0.0
    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    fine_adjust: bool = False
    action_edges: tuple[InputAction, ...] = ()
    drop_held: bool = False

    def __post_init__(self) -> None:
        if type(self.drop_held) is not bool:
            raise TypeError("drop_held must be a boolean")
        if not isfinite(self.analog_x) or not -1.0 <= self.analog_x <= 1.0:
            raise ValueError("analog_x must be finite and normalized to [-1, 1]")
        if not isfinite(self.analog_y) or not -1.0 <= self.analog_y <= 1.0:
            raise ValueError("analog_y must be finite and normalized to [-1, 1]")
        if not isinstance(self.action_edges, tuple):
            raise TypeError("action_edges must be an immutable tuple")
        if any(not isinstance(action, InputAction) for action in self.action_edges):
            raise TypeError("action_edges must contain InputAction values")
        if any(
            action in (InputAction.NAV_UP, InputAction.NAV_DOWN)
            for action in self.action_edges
        ):
            raise ValueError("navigation actions are generated from the menu axis")


class InputAdapter(Protocol):
    """Stable boundary implemented by a keyboard or native-device adapter."""

    def poll(self) -> InputSample: ...


@dataclass(frozen=True, slots=True)
class ManagedInput:
    """Normalized scene input plus the requested gameplay movement speed."""

    frame: InputFrame
    horizontal_velocity: float


class InputManager:
    """Select exactly one backend and translate its samples to game actions."""

    NAV_ACTIVATE_THRESHOLD = 0.55
    NAV_RELEASE_THRESHOLD = 0.35
    NAV_INITIAL_DELAY = 0.28
    NAV_REPEAT_INTERVAL = 0.11

    def __init__(self) -> None:
        self._adapters: dict[InputBackend, InputAdapter] = {}
        self._active_backend: InputBackend | None = None
        self._next_sequence = 0
        self._nav_direction = 0
        self._nav_repeat_remaining = 0.0

    @property
    def active_backend(self) -> InputBackend | None:
        return self._active_backend

    def register_adapter(self, backend: InputBackend, adapter: InputAdapter) -> None:
        """Register or replace an adapter; registration never selects it."""
        self._adapters[backend] = adapter

    def select_backend(self, backend: InputBackend | None) -> None:
        """Select one source, or `None` to disable all sources."""
        if backend is not None and backend not in self._adapters:
            raise ValueError(f"no adapter registered for backend {backend.value}")
        self._active_backend = backend
        self.reset()

    def reset(self) -> None:
        """Clear UI navigation state after pause, focus loss, or disconnect."""
        self._nav_direction = 0
        self._nav_repeat_remaining = 0.0

    def poll(self, ui_delta_seconds: float) -> ManagedInput:
        """Poll the selected source and produce one immutable semantic frame."""
        if not isfinite(ui_delta_seconds) or ui_delta_seconds < 0.0:
            raise ValueError("UI delta must be finite and non-negative")

        sample = (
            self._adapters[self._active_backend].poll()
            if self._active_backend is not None
            else InputSample()
        )
        if not isinstance(sample, InputSample):
            raise TypeError("input adapter poll() must return InputSample")

        move_x, horizontal_velocity = select_horizontal_axis(
            sample.analog_x,
            left=sample.left,
            right=sample.right,
            fine_adjust=sample.fine_adjust,
        )
        move_y = select_vertical_axis(
            sample.analog_y,
            up=sample.up,
            down=sample.down,
        )

        edges = [self._new_edge(action) for action in sample.action_edges]
        navigation_action = self._update_navigation(move_y, ui_delta_seconds)
        if navigation_action is not None:
            edges.append(self._new_edge(navigation_action))

        return ManagedInput(
            frame=InputFrame(
                move_x=move_x,
                move_y=move_y,
                fine_adjust=sample.fine_adjust,
                edges=tuple(edges),
                drop_held=sample.drop_held,
            ),
            horizontal_velocity=horizontal_velocity,
        )

    def _new_edge(self, action: InputAction) -> InputEdge:
        edge = InputEdge(sequence=self._next_sequence, action=action)
        self._next_sequence += 1
        return edge

    def _update_navigation(self, move_y: float, delta_seconds: float) -> InputAction | None:
        threshold_direction = (
            -1
            if move_y <= -self.NAV_ACTIVATE_THRESHOLD
            else 1
            if move_y >= self.NAV_ACTIVATE_THRESHOLD
            else 0
        )
        emitted_direction = 0

        if self._nav_direction == 0:
            if threshold_direction:
                self._nav_direction = threshold_direction
                self._nav_repeat_remaining = self.NAV_INITIAL_DELAY
                emitted_direction = threshold_direction
        elif threshold_direction and threshold_direction != self._nav_direction:
            self._nav_direction = threshold_direction
            self._nav_repeat_remaining = self.NAV_INITIAL_DELAY
            emitted_direction = threshold_direction
        elif abs(move_y) < self.NAV_RELEASE_THRESHOLD:
            self._nav_direction = 0
            self._nav_repeat_remaining = 0.0
        else:
            self._nav_repeat_remaining -= delta_seconds
            if self._nav_repeat_remaining <= 1e-9:
                emitted_direction = self._nav_direction
                self._nav_repeat_remaining = self.NAV_REPEAT_INTERVAL

        if emitted_direction < 0:
            return InputAction.NAV_UP
        if emitted_direction > 0:
            return InputAction.NAV_DOWN
        return None
