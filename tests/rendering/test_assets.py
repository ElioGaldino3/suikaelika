from __future__ import annotations

from types import SimpleNamespace

import pytest

pygame = pytest.importorskip("pygame")

from suika_elika.app import _MenuCanvas  # noqa: E402
from suika_elika.contracts import RoundState, SessionSnapshot  # noqa: E402
from suika_elika.game.catalog import load_catalog  # noqa: E402
from suika_elika.rendering.assets import ASSET_ROOT, GameArt  # noqa: E402
from suika_elika.rendering.renderer import Renderer  # noqa: E402
from tools.process_art_assets import (  # noqa: E402
    FRUIT_CELLS,
    FRUIT_SHEET,
    FRUIT_SHEET_SIZE,
    SPRITE_RADIUS,
    pack_round_sprite,
    process_fruit_sprites,
)


def test_art_pipeline_uses_new_transparent_sheet_and_nonoverlapping_crop_cells() -> None:
    sheet = pygame.image.load(FRUIT_SHEET)
    assert sheet.get_size() == FRUIT_SHEET_SIZE == (1448, 1086)
    assert sheet.get_at((0, 0)).a == 0
    assert len(FRUIT_CELLS) == 11

    cells = tuple(FRUIT_CELLS.values())
    for index, first in enumerate(cells):
        x1, y1, x2, y2 = first
        assert 0 <= x1 < x2 <= FRUIT_SHEET_SIZE[0]
        assert 0 <= y1 < y2 <= FRUIT_SHEET_SIZE[1]
        for second in cells[index + 1 :]:
            other_x1, other_y1, other_x2, other_y2 = second
            assert x2 <= other_x1 or other_x2 <= x1 or y2 <= other_y1 or other_y2 <= y1


def test_historical_sheet_extraction_keeps_original_crop_resolution(tmp_path) -> None:
    sheet = pygame.image.load(FRUIT_SHEET)
    sprite_dir = tmp_path / "sprites"

    process_fruit_sprites(sheet, sprite_dir)

    assert {path.stem for path in sprite_dir.glob("*.png")} == set(FRUIT_CELLS)
    for fruit_id in FRUIT_CELLS:
        generated = pygame.image.load(sprite_dir / f"{fruit_id}.png")
        bounds = generated.get_bounding_rect(min_alpha=32)
        assert bounds.width > 0
        assert bounds.left >= 8 and bounds.top >= 8
        assert bounds.right <= generated.get_width() - 8
        assert bounds.bottom <= generated.get_height() - 8
        x1, y1, x2, y2 = FRUIT_CELLS[fruit_id]
        assert generated.get_size() == (bounds.width + 16, bounds.height + 16)
        assert generated.get_width() <= x2 - x1 + 16
        assert generated.get_height() <= y2 - y1 + 16


def test_all_packaged_fruits_are_512_square_with_a_filled_circular_silhouette() -> None:
    for entry in load_catalog().entries:
        source = pygame.image.load(ASSET_ROOT / "sprites" / f"{entry.fruit_id}.png")
        assert source.get_size() == (512, 512), entry.fruit_id
        assert source.get_flags() & pygame.SRCALPHA
        assert source.get_at((0, 0)).a == 0
        mask = pygame.mask.from_surface(source, 220)
        inner = pygame.Surface(source.get_size(), pygame.SRCALPHA, 32)
        pygame.draw.circle(inner, (255, 255, 255, 255), (256, 256), SPRITE_RADIUS - 2)
        required = pygame.mask.from_surface(inner)
        assert mask.overlap_area(required, (0, 0)) == required.count(), entry.fruit_id
        outline = (
            point
            for component in pygame.mask.from_surface(source, 32).connected_components()
            for point in component.outline()
        )
        distances = [((x + 0.5 - 256) ** 2 + (y + 0.5 - 256) ** 2) ** 0.5 for x, y in outline]
        assert min(distances) >= SPRITE_RADIUS - 1, entry.fruit_id
        assert max(distances) <= SPRITE_RADIUS + 1, entry.fruit_id


def test_round_sprite_packing_rejects_empty_or_nonround_art() -> None:
    empty = pygame.Surface((100, 100), pygame.SRCALPHA, 32)
    with pytest.raises(ValueError, match="no opaque pixels"):
        pack_round_sprite(empty)
    elongated = pygame.Surface((100, 200), pygame.SRCALPHA, 32)
    elongated.fill((255, 0, 0, 255))
    with pytest.raises(ValueError, match="round silhouette"):
        pack_round_sprite(elongated)


def test_larger_fruit_source_pngs_retain_high_resolution_crop() -> None:
    watermelon = pygame.image.load(ASSET_ROOT / "sprites" / "watermelon.png")
    radius = load_catalog().get("watermelon").definition.radius
    render_side = 2 * (radius + max(7, round(radius * 0.28)))

    assert watermelon.get_width() >= render_side
    assert watermelon.get_height() >= render_side
    bounds = watermelon.get_bounding_rect(min_alpha=32)
    assert bounds.left > 0 and bounds.top > 0
    assert bounds.right < watermelon.get_width()
    assert bounds.bottom < watermelon.get_height()


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


def test_imported_fruit_silhouettes_fit_their_physics_circles() -> None:
    catalog = load_catalog()
    sprites = GameArt().fruit_surfaces(catalog)

    for entry in catalog.entries:
        sprite = sprites[entry.fruit_id]
        mask = pygame.mask.from_surface(sprite, 32)
        center_x = sprite.get_width() / 2
        center_y = sprite.get_height() / 2
        outline = (
            point
            for component in mask.connected_components()
            for point in component.outline()
        )
        distances = [
            ((x + 0.5 - center_x) ** 2 + (y + 0.5 - center_y) ** 2) ** 0.5
            for x, y in outline
        ]
        visible_radius = max(distances, default=0.0)

        assert visible_radius == pytest.approx(entry.definition.radius, abs=1.5)
        assert min(distances) == pytest.approx(entry.definition.radius, abs=1.5)


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
        disabled_indices=(),
        preview_fruit_id=None,
    )

    canvas.draw_menu(snapshot)

    assert canvas._background is not None
    expected = pygame.image.load(ASSET_ROOT / "backgrounds" / "menu.png")
    assert target.get_at((4, 4)) == expected.get_at((4, 4))
    assert target.get_at((640, 360)) != expected.get_at((640, 360))


def test_menu_canvas_draws_selected_fruit_and_scaled_hitbox_preview() -> None:
    target = pygame.Surface((1280, 720))
    canvas = _MenuCanvas(pygame, target)
    snapshot = SimpleNamespace(
        message="",
        footer="←/→ Ajustar",
        subtitle="Maçã: raio 39.7 · padrão 37.8 · aplica ao reiniciar",
        choices=tuple(f"Fruta {index}: 105%" for index in range(11))
        + ("Restaurar padrões", "Voltar às opções"),
        selected_index=4,
        title="Ajustar hitboxes",
        disabled_indices=(),
        preview_fruit_id="apple",
        preview_hitbox_scale=1.05,
        preview_base_radius=37.8,
    )

    canvas.draw_menu(snapshot)

    assert canvas._preview_art is not None
    assert canvas._preview_surfaces["apple"] is not None
    assert any(
        target.get_at((x, y))[:3] == (40, 255, 120)
        for x in range(900, 1000)
        for y in range(250, 450)
    )


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
