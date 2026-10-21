"""Resource bounds for surfaces reused on every presentation frame."""

from __future__ import annotations

from math import pi

import pytest

pygame = pytest.importorskip("pygame")

from suika_elika.contracts import (  # noqa: E402
    EventType,
    RoundState,
    SessionSnapshot,
    Vector2,
    make_event,
)
from suika_elika.game.catalog import load_catalog  # noqa: E402
from suika_elika.rendering.effects import MAX_PARTICLES, EffectSystem  # noqa: E402
from suika_elika.rendering.renderer import Renderer  # noqa: E402


def test_renderer_reuses_fixed_size_presentation_and_pause_surfaces() -> None:
    target = pygame.Surface((1280, 720))
    renderer = Renderer(target)
    current = load_catalog().get("cherry").definition
    snapshot = SessionSnapshot(
        score=0,
        high_score=0,
        current_fruit=current,
        next_fruit=current,
        fruits=(),
        launcher_x=400,
        drop_ready=True,
        danger_progress=0.0,
        round_state=RoundState.PAUSED,
    )

    renderer.draw_session(snapshot, ())
    scaled_surface = renderer._scaled_surface
    state_veil = renderer._state_veil

    for _ in range(99):
        renderer.draw_session(snapshot, ())

    assert scaled_surface is not None
    assert renderer._scaled_surface is scaled_surface
    assert renderer._scaled_surface.get_size() == (1152, 648)
    assert renderer._state_veil is state_veil
    assert renderer._state_veil.get_size() == (1280, 720)
    assert len(renderer._small_fruit_surfaces) <= 1


def test_renderer_reuses_quantized_fruit_rotation_surfaces() -> None:
    renderer = Renderer(pygame.Surface((1280, 720)))
    definition = load_catalog().get("cherry").definition

    renderer._draw_fruit(
        definition, Vector2(100, 100), angle=0.20, world_coordinates=False
    )
    cached = next(iter(renderer._rotated_fruit_surfaces.values()))
    renderer._draw_fruit(
        definition, Vector2(100, 100), angle=0.21, world_coordinates=False
    )

    assert len(renderer._rotated_fruit_surfaces) == 1
    assert next(iter(renderer._rotated_fruit_surfaces.values())) is cached


def test_renderer_rotation_surface_cache_stays_bounded() -> None:
    renderer = Renderer(pygame.Surface((1280, 720)))
    entries = load_catalog().entries[:6]

    for entry in entries:
        for rotation_step in range(1, 24):
            renderer._draw_fruit(
                entry.definition,
                Vector2(100, 100),
                angle=rotation_step * 2 * pi / 24,
                world_coordinates=False,
            )

    assert len(renderer._rotated_fruit_surfaces) == 128


def test_effect_particle_memory_remains_capped_after_many_events() -> None:
    effects = EffectSystem(seed=7)
    for step in range(500):
        event = make_event(
            EventType.FRUIT_MERGED,
            step,
            entity_ids=(f"a-{step}", f"b-{step}", f"c-{step}"),
            position=Vector2(400.0, 120.0),
        )
        effects.update(0.0, (event,))

    assert len(effects.particles) == MAX_PARTICLES
    assert len(effects._seen_events) <= 512
    assert len(effects._seen_order) <= 512
