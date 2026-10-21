"""Runtime settings for the Pygame application."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Presentation and fixed-step limits owned by the application loop."""

    window_size: tuple[int, int] = (1280, 720)
    target_fps: int = 60
    fixed_dt: float = 1.0 / 120.0
    max_frame_delta: float = 0.25
    max_simulation_steps: int = 8
    fullscreen: bool = True
    allow_keyboard_fallback: bool = False
    player_indexes: tuple[int, int] | None = None
    debug_colliders: bool = False

    def __post_init__(self) -> None:
        if (
            len(self.window_size) != 2
            or any(type(value) is not int or value <= 0 for value in self.window_size)
        ):
            raise ValueError("window_size must contain two positive integers")
        if type(self.target_fps) is not int or self.target_fps <= 0:
            raise ValueError("target_fps must be a positive integer")
        if (
            not isfinite(self.fixed_dt)
            or self.fixed_dt <= 0
            or not isfinite(self.max_frame_delta)
            or self.max_frame_delta <= 0
        ):
            raise ValueError("frame timing values must be finite and positive")
        if type(self.max_simulation_steps) is not int or self.max_simulation_steps <= 0:
            raise ValueError("max_simulation_steps must be a positive integer")
        if (
            type(self.fullscreen) is not bool
            or type(self.allow_keyboard_fallback) is not bool
            or type(self.debug_colliders) is not bool
        ):
            raise TypeError("fullscreen, keyboard fallback, and debug colliders must be booleans")
        if self.player_indexes is not None and (
            len(self.player_indexes) != 2
            or any(type(index) is not int or index < 0 for index in self.player_indexes)
            or self.player_indexes[0] == self.player_indexes[1]
        ):
            raise ValueError("player_indexes must contain two distinct non-negative indices")


__all__ = ["AppConfig"]
