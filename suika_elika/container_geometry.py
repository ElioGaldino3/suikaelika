"""Shared bowl outline geometry for the physics world and renderer."""

from __future__ import annotations

from math import ceil


def bowl_edge(width: float, height: float) -> int:
    """Match the procedural bowl's border size for its physical dimensions."""
    return max(4, ceil(min(width, height) * 0.012))


def bowl_outline_points(
    width: float, height: float, edge: float
) -> tuple[tuple[float, float], ...]:
    """Return the open-top bowl outline with a shallow curved bottom profile."""
    return (
        (edge * 2, edge),
        (width - edge * 2, edge),
        (width - edge * 2, height - edge * 3),
        (width * 3 / 4, height - edge),
        (width / 4, height - edge),
        (edge * 2, height - edge * 3),
    )


__all__ = ["bowl_edge", "bowl_outline_points"]
