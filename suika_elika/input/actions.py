"""Pure normalization helpers for semantic input adapters."""

from __future__ import annotations

from math import isfinite, pow

DEFAULT_DEADZONE = 0.20
DEFAULT_RESPONSE_EXPONENT = 1.3
ANALOG_SPEED = 520.0
DIGITAL_SPEED = 420.0
FINE_SPEED = 100.0


def normalize_axis(
    value: float,
    *,
    deadzone: float = DEFAULT_DEADZONE,
    exponent: float = DEFAULT_RESPONSE_EXPONENT,
) -> float:
    """Apply the project's radial-axis response curve to one normalized axis."""
    if not isfinite(value) or not -1.0 <= value <= 1.0:
        raise ValueError("axis value must be finite and normalized to [-1, 1]")
    if not isfinite(deadzone) or not 0.0 <= deadzone < 1.0:
        raise ValueError("deadzone must be finite and in [0, 1)")
    if not isfinite(exponent) or exponent <= 0.0:
        raise ValueError("response exponent must be finite and positive")

    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    curved = pow((magnitude - deadzone) / (1.0 - deadzone), exponent)
    return curved if value > 0.0 else -curved


def resolve_digital_axis(negative: bool, positive: bool) -> int:
    """Return -1/0/1; opposite directions cancel instead of summing."""
    if negative == positive:
        return 0
    return -1 if negative else 1


def select_horizontal_axis(
    analog_x: float,
    *,
    left: bool = False,
    right: bool = False,
    fine_adjust: bool = False,
) -> tuple[float, float]:
    """Return normalized horizontal intent and its requested units/second.

    Any active digital direction takes priority over the analog stick. This also
    makes simultaneous left+right cancel to neutral without falling through to
    the stick value.
    """
    if left or right:
        digital = float(resolve_digital_axis(left, right))
        speed_limit = FINE_SPEED if fine_adjust else DIGITAL_SPEED
        return digital, digital * speed_limit

    normalized = normalize_axis(analog_x)
    speed_limit = FINE_SPEED if fine_adjust else ANALOG_SPEED
    return normalized, normalized * speed_limit


def select_vertical_axis(
    analog_y: float,
    *,
    up: bool = False,
    down: bool = False,
) -> float:
    """Return the menu axis, with D-pad directions taking priority."""
    if up or down:
        return float(resolve_digital_axis(up, down))
    if not isfinite(analog_y) or not -1.0 <= analog_y <= 1.0:
        raise ValueError("axis value must be finite and normalized to [-1, 1]")
    return analog_y
