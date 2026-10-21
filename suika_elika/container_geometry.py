"""Shared bowl outline geometry for the physics world and renderer."""

from __future__ import annotations

from math import ceil


def bowl_edge(width: float, height: float) -> int:
    """Match the procedural bowl's border size for its physical dimensions."""
    return max(4, ceil(min(width, height) * 0.012))


def bowl_outline_points(
    width: float, height: float, edge: float
) -> tuple[tuple[float, float], ...]:
    """Return the open-top rectangular basket outline with a flat floor."""
    return (
        (0.0, edge),
        (width, edge),
        (width, height - edge),
        (0.0, height - edge),
    )


__all__ = ["bowl_edge", "bowl_outline_points"]
