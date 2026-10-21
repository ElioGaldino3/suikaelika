"""Aspect-preserving transforms between logical game and physical screen space."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from suika_elika.contracts import Vector2

LOGICAL_WIDTH = 1280.0
LOGICAL_HEIGHT = 720.0
DEFAULT_SAFE_AREA_FRACTION = 0.05


@dataclass(frozen=True, slots=True)
class ViewportRect:
    """A floating-point screen-space rectangle, suitable for draw and clip bounds."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(not isfinite(value) for value in values):
            raise ValueError("viewport rectangle values must be finite")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("viewport rectangle dimensions must be positive")


@dataclass(frozen=True, slots=True)
class Viewport:
    """Uniformly scale and center the logical canvas inside a physical display.

    Points outside the letterboxed canvas still convert to logical coordinates;
    callers can use ``screen_rect`` to decide whether pointer input is in bounds.
    """

    screen_width: float
    screen_height: float
    logical_width: float = LOGICAL_WIDTH
    logical_height: float = LOGICAL_HEIGHT
    safe_area_fraction: float = DEFAULT_SAFE_AREA_FRACTION

    def __post_init__(self) -> None:
        dimensions = (
            self.screen_width,
            self.screen_height,
            self.logical_width,
            self.logical_height,
        )
        if any(not isfinite(value) or value <= 0 for value in dimensions):
            raise ValueError("screen and logical dimensions must be finite and positive")
        if (
            not isfinite(self.safe_area_fraction)
            or not 0 <= self.safe_area_fraction <= 0.25
        ):
            raise ValueError("safe area fraction must be finite and in [0, 0.25]")

    @property
    def scale(self) -> float:
        """The single scale factor that preserves logical aspect ratio."""
        return min(
            self.screen_width / self.logical_width,
            self.screen_height / self.logical_height,
        )

    @property
    def render_width(self) -> float:
        return self.logical_width * self.scale

    @property
    def render_height(self) -> float:
        return self.logical_height * self.scale

    @property
    def offset_x(self) -> float:
        return (self.screen_width - self.render_width) / 2

    @property
    def offset_y(self) -> float:
        return (self.screen_height - self.render_height) / 2

    @property
    def screen_rect(self) -> ViewportRect:
        """The centered screen-space bounds of the complete logical canvas."""
        return ViewportRect(
            self.offset_x,
            self.offset_y,
            self.render_width,
            self.render_height,
        )

    @property
    def safe_rect(self) -> ViewportRect:
        """Screen-space bounds for essential UI, inset from each logical edge."""
        inset_x = self.logical_width * self.safe_area_fraction * self.scale
        inset_y = self.logical_height * self.safe_area_fraction * self.scale
        return ViewportRect(
            self.offset_x + inset_x,
            self.offset_y + inset_y,
            self.render_width - 2 * inset_x,
            self.render_height - 2 * inset_y,
        )

    def logical_to_screen(self, point: Vector2) -> Vector2:
        """Transform a logical coordinate to its physical screen coordinate."""
        return Vector2(
            self.offset_x + point.x * self.scale,
            self.offset_y + point.y * self.scale,
        )

    def screen_to_logical(self, point: Vector2) -> Vector2:
        """Transform a screen coordinate, including letterbox space, to logical."""
        return Vector2(
            (point.x - self.offset_x) / self.scale,
            (point.y - self.offset_y) / self.scale,
        )


__all__ = [
    "DEFAULT_SAFE_AREA_FRACTION",
    "LOGICAL_HEIGHT",
    "LOGICAL_WIDTH",
    "Viewport",
    "ViewportRect",
]
