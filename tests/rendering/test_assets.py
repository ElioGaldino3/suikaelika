from __future__ import annotations

from types import SimpleNamespace

import pytest

pygame = pytest.importorskip("pygame")

from suika_elika.app import _MenuCanvas  # noqa: E402
from suika_elika.contracts import RoundState, SessionSnapshot  # noqa: E402
from suika_elika.game.catalog import load_catalog  # noqa: E402
from suika_elika.rendering.assets import ASSET_ROOT, GameArt  # noqa: E402
from suika_elika.rendering.renderer import Renderer  # noqa: E402


def test_imported_fruit_sprites_match_catalog_and_have_transparency() -> None:
    catalog = load_catalog()
    art = GameArt()
    sprites = art.fruit_surfaces(catalog)

    assert set(sprites) == {entry.fruit_id for entry in catalog.entries}
    assert len(sprites) == 11
    for entry in catalog.entries:
        sprite = sprites[entry.fruit_id]
        assert sprite.get_flags() & pygame.SRCALPHA
        assert sprite.get_at((0, 0)).a == 0
        assert sprite.get_at((sprite.get_width() // 2, sprite.get_height() // 2)).a > 0
        assert art.fruit_surfaces(catalog)[entry.fruit_id] is sprite


def test_missing_assets_use_the_existing_procedural_art(tmp_path) -> None:
    art = GameArt(tmp_path)
    catalog = load_catalog()

    sprites = art.fruit_surfaces(catalog)
    background = art.background_surface((640, 360))

    assert len(sprites) == 11
    assert background.get_size() == (640, 360)
    assert background is art.background_surface((640, 360))


def test_imported_backgrounds_are_cached_at_requested_dimensions() -> None:
    art = GameArt()

    gameplay = art.background_surface((960, 540))
    menu = art.background_surface((960, 540), menu=True)

    assert gameplay.get_size() == menu.get_size() == (960, 540)
    assert gameplay is art.background_surface((960, 540))
    assert menu is art.background_surface((960, 540), menu=True)
    assert gameplay.get_at((480, 270)) != menu.get_at((480, 270))


def test_menu_canvas_uses_menu_background_behind_readable_panel() -> None:
    target = pygame.Surface((1280, 720))
    canvas = _MenuCanvas(pygame, target)
    snapshot = SimpleNamespace(
        message="",
        footer="",
        subtitle="",
        choices=("Jogar",),
        selected_index=0,
        title="Suika Elika",
    )

    canvas.draw_menu(snapshot)

    assert canvas._background is not None
    expected = pygame.image.load(ASSET_ROOT / "backgrounds" / "menu.png")
    assert target.get_at((4, 4)) == expected.get_at((4, 4))
    assert target.get_at((640, 360)) != expected.get_at((640, 360))


def test_renderer_draws_the_gameplay_background_and_imported_sprites() -> None:
    target = pygame.Surface((1280, 720))
    renderer = Renderer(target)

    assert renderer._fruit_surfaces["cherry"].get_at((0, 0)).a == 0
    expected = renderer.art.background_surface((1280, 720))
    catalog = load_catalog()
    snapshot = SessionSnapshot(
        score=0,
        high_score=0,
        current_fruit=catalog.get("cherry").definition,
        next_fruit=catalog.get("strawberry").definition,
        fruits=(),
        launcher_x=400,
        drop_ready=True,
        danger_progress=0,
        round_state=RoundState.PLAYING,
    )
    renderer.draw_session(snapshot, ())

    actual_pixel = target.get_at((68, 40))
    source_pixel = expected.get_at((4, 4))
    assert sum(
        abs(actual - source)
        for actual, source in zip(actual_pixel, source_pixel, strict=True)
    ) <= 10
