from __future__ import annotations

import pytest

from suika_elika.contracts import Vector2
from suika_elika.rendering.viewport import Viewport, ViewportRect


@pytest.mark.parametrize(
    ("size", "expected_scale", "expected_origin"),
    [
        ((1280, 720), 1, (0, 0)),
        ((1920, 1080), 1.5, (0, 0)),
        ((3840, 2160), 3, (0, 0)),
        ((640, 480), 0.5, (0, 60)),
        ((1024, 768), 0.8, (0, 96)),
    ],
)
def test_viewport_preserves_aspect_and_centers_content(
    size: tuple[int, int], expected_scale: float, expected_origin: tuple[float, float]
) -> None:
    viewport = Viewport(*size)

    assert viewport.scale == pytest.approx(expected_scale)
    assert viewport.screen_rect == ViewportRect(
        expected_origin[0], expected_origin[1], 1280 * expected_scale, 720 * expected_scale
    )
    assert viewport.render_width / viewport.render_height == pytest.approx(16 / 9)


@pytest.mark.parametrize("size", [(1920, 1080), (3840, 2160), (640, 480), (720, 720)])
def test_coordinate_conversions_round_trip_without_distorting_circles(
    size: tuple[int, int],
) -> None:
    viewport = Viewport(*size)
    logical_point = Vector2(380, 164)

    physical_point = viewport.logical_to_screen(logical_point)
    restored = viewport.screen_to_logical(physical_point)

    assert restored.x == pytest.approx(logical_point.x)
    assert restored.y == pytest.approx(logical_point.y)
    assert viewport.scale == pytest.approx(viewport.render_width / 1280)
    assert viewport.scale == pytest.approx(viewport.render_height / 720)


def test_4_by_3_letterbox_coordinates_convert_back_and_safe_area_is_inset() -> None:
    viewport = Viewport(640, 480, safe_area_fraction=0.05)

    assert viewport.screen_rect == ViewportRect(0, 60, 640, 360)
    assert viewport.screen_to_logical(Vector2(0, 60)) == Vector2(0, 0)
    assert viewport.screen_to_logical(Vector2(640, 420)) == Vector2(1280, 720)
    assert viewport.safe_rect == ViewportRect(32, 78, 576, 324)


def test_safe_area_accepts_persisted_settings_upper_bound() -> None:
    viewport = Viewport(1280, 720, safe_area_fraction=0.25)

    assert viewport.safe_rect == ViewportRect(320, 180, 640, 360)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"screen_width": 0, "screen_height": 720},
        {"screen_width": 1280, "screen_height": float("inf")},
        {"screen_width": 1280, "screen_height": 720, "logical_width": -1},
        {"screen_width": 1280, "screen_height": 720, "safe_area_fraction": -0.01},
        {"screen_width": 1280, "screen_height": 720, "safe_area_fraction": 0.26},
    ],
)
def test_invalid_viewport_dimensions_and_safe_area_are_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        Viewport(**kwargs)


def test_non_finite_coordinates_are_rejected_by_vector_contract() -> None:
    viewport = Viewport(1280, 720)
    with pytest.raises(ValueError, match="finite"):
        viewport.logical_to_screen(Vector2(float("nan"), 0))
