from __future__ import annotations

import pytest

from suika_elika.game.catalog import load_catalog
from suika_elika.rendering.procedural import ProceduralArt

pygame = pytest.importorskip("pygame")


@pytest.fixture
def art() -> ProceduralArt:
    return ProceduralArt()


def test_fruit_surfaces_cover_catalog_and_are_cached(art: ProceduralArt) -> None:
    catalog = load_catalog()

    surfaces = art.fruit_surfaces(catalog)

    assert set(surfaces) == {entry.fruit_id for entry in catalog.entries}
    assert len(surfaces) == 11
    for entry in catalog.entries:
        radius = round(entry.definition.radius)
        margin = max(7, -(-radius * 28 // 100))
        expected_size = (2 * (radius + margin),) * 2
        surface = surfaces[entry.fruit_id]
        assert surface.get_size() == expected_size
        assert surface.get_at((surface.get_width() // 2, surface.get_height() // 2)).a > 0
        bounds = surface.get_bounding_rect()
        assert bounds.left > 0 and bounds.top > 0
        assert bounds.right < surface.get_width() and bounds.bottom < surface.get_height()
        assert art.fruit_surface(entry) is surface


def test_fruit_palette_colors_are_present_in_rendered_surfaces(art: ProceduralArt) -> None:
    catalog = load_catalog()

    for entry in catalog.entries:
        surface = art.fruit_surface(entry)
        expected_rgb = tuple(int(entry.color[index : index + 2], 16) for index in (1, 3, 5))
        close_to_palette = sum(
            sum(
                abs(actual - expected)
                for actual, expected in zip(surface.get_at((x, y))[:3], expected_rgb, strict=True)
            )
            <= 8
            for x in range(surface.get_width())
            for y in range(surface.get_height())
        )
        assert close_to_palette >= 5, entry.fruit_id


def test_container_and_background_have_requested_dimensions_and_cache(art: ProceduralArt) -> None:
    container = art.container_surface((640, 400))
    background = art.background_surface((960, 540))

    assert container.get_size() == (640, 400)
    assert background.get_size() == (960, 540)
    assert art.container_surface((640, 400)) is container
    assert art.background_surface((960, 540)) is background
    assert container.get_flags() & pygame.SRCALPHA
    center = container.get_at((320, 200))
    assert 0 < center.a < 255


@pytest.mark.parametrize("size", [(0, 10), (10, -1), (1.5, 3), (10,), (1, 2, 3)])
def test_scene_surface_sizes_must_be_two_positive_integers(
    art: ProceduralArt, size: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError, match="two positive integers"):
        art.container_surface(size)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="two positive integers"):
        art.background_surface(size)  # type: ignore[arg-type]
