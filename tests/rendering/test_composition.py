"""Headless checks for rendered composition, effects, and PlayScene cadence."""

from __future__ import annotations

import pytest

pygame = pytest.importorskip("pygame")

from suika_elika.contracts import (  # noqa: E402
    BodySnapshot,
    ContactSnapshot,
    DomainEvent,
    EventType,
    FruitDefinition,
    FruitSnapshot,
    InputAction,
    InputEdge,
    InputFrame,
    Pose,
    RoundState,
    SessionSnapshot,
    Vector2,
    make_event,
)
from suika_elika.game.session import GameSession  # noqa: E402
from suika_elika.rendering.effects import MAX_PARTICLES, EffectSystem  # noqa: E402
from suika_elika.rendering.renderer import (  # noqa: E402
    DEBUG_BOUNDS_COLOR,
    DEBUG_COLLIDER_COLOR,
    WORLD_ORIGIN,
    Renderer,
)
from suika_elika.scenes.play import PlayScene  # noqa: E402

_ZERO = Vector2(0, 0)


class FakePhysics:
    def __init__(self) -> None:
        self.bodies: dict[str, tuple[object, Pose, Vector2]] = {}
        self.steps = 0
        self._contacts: tuple[ContactSnapshot, ...] = ()

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 = _ZERO,
        angular_velocity: float = 0.0,
    ) -> None:
        del angular_velocity
        self.bodies[entity_id] = (definition, pose, velocity)

    def remove_body(self, entity_id: str) -> None:
        self.bodies.pop(entity_id, None)

    def step(self) -> None:
        self.steps += 1
        self._contacts = ()

    def contacts(self) -> tuple[ContactSnapshot, ...]:
        return self._contacts

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        del center, radius
        return ()

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[BodySnapshot, ...]:
        return tuple(
            BodySnapshot(entity_id, pose, velocity)
            for entity_id in entity_ids
            if (body := self.bodies.get(entity_id)) is not None
            for _, pose, velocity in (body,)
        )


def _snapshot(*, angle: float = 0.0) -> SessionSnapshot:
    from suika_elika.game.catalog import load_catalog

    catalog = load_catalog()
    return SessionSnapshot(
        score=12,
        high_score=40,
        current_fruit=catalog.get("cherry").definition,
        next_fruit=catalog.get("lemon").definition,
        fruits=(
            FruitSnapshot(
                "fruit-1",
                "cherry",
                Pose(Vector2(400, 120), angle - 0.2),
                Pose(Vector2(404, 124), angle),
                True,
                0.4,
            ),
        ),
        launcher_x=400,
        drop_ready=False,
        danger_progress=0.5,
        round_state=RoundState.PLAYING,
    )


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (640, 480)])
def test_renderer_composes_a_snapshot_to_letterboxed_target(size: tuple[int, int]) -> None:
    target = pygame.Surface(size)
    renderer = Renderer(target)
    renderer.set_round_metrics(best_fruit_level=4, watermelons=1, duration_seconds=65)
    renderer.advance_presentation(1 / 60)
    renderer.draw_session(_snapshot(), ())

    assert target.get_size() == size
    assert target.get_at((size[0] // 2, size[1] // 2)).a == 255


def test_renderer_interpolates_poses_and_rejects_invalid_alpha() -> None:
    renderer = Renderer(pygame.Surface((1280, 720)))
    renderer.set_interpolation_alpha(0.25)
    assert renderer.interpolation_alpha == 0.25
    with pytest.raises(ValueError, match="interpolation alpha"):
        renderer.set_interpolation_alpha(1.1)
    renderer.draw_session(_snapshot(angle=3.13), ())
    renderer.draw_session(_snapshot(angle=-3.13), ())


def test_renderer_applies_safe_area_to_the_presentation_bounds() -> None:
    target = pygame.Surface((1280, 720))
    renderer = Renderer(target, safe_area_fraction=0.05)

    renderer.draw_session(_snapshot(), ())

    x, y, width, height = renderer.presentation_rect
    assert x == pytest.approx(64, abs=1)
    assert y == pytest.approx(36, abs=1)
    assert width == pytest.approx(1152, abs=1)
    assert height == pytest.approx(648, abs=1)


def test_debug_renderer_draws_physics_circle_and_bounding_box() -> None:
    renderer = Renderer(pygame.Surface((1280, 720)), debug_colliders=True)
    snapshot = _snapshot()
    fruit = snapshot.fruits[0]
    definition = renderer.catalog.get(fruit.fruit_id).definition
    center = (
        round(WORLD_ORIGIN.x + fruit.current_pose.position.x),
        round(WORLD_ORIGIN.y + fruit.current_pose.position.y),
    )
    radius = round(definition.radius)

    renderer.draw_session(snapshot, ())

    assert (
        renderer._logical.get_at((center[0] + radius - 1, center[1]))[:3]
        == DEBUG_COLLIDER_COLOR
    )
    assert (
        renderer._logical.get_at((center[0] - radius, center[1] - radius))[:3]
        == DEBUG_BOUNDS_COLOR
    )


def test_debug_circle_tracks_adjusted_catalog_without_resizing_fruit_art() -> None:
    renderer = Renderer(pygame.Surface((1280, 720)), debug_colliders=True)
    original_sprite_size = renderer._fruit_surfaces["cherry"].get_size()
    renderer.set_catalog(renderer.catalog.with_hitbox_scales((("cherry", 1.5),)))
    snapshot = _snapshot()
    fruit = snapshot.fruits[0]
    center = (
        round(WORLD_ORIGIN.x + fruit.current_pose.position.x),
        round(WORLD_ORIGIN.y + fruit.current_pose.position.y),
    )

    renderer.draw_session(snapshot, ())

    assert renderer.catalog.get("cherry").definition.radius == 21
    assert renderer._fruit_surfaces["cherry"].get_size() == original_sprite_size
    assert renderer._logical.get_at((center[0] + 20, center[1]))[:3] == DEBUG_COLLIDER_COLOR


def test_effects_are_bounded_independent_and_consume_each_event_once() -> None:
    event = make_event(
        EventType.FRUIT_MERGED,
        4,
        entity_ids=("a", "b", "c"),
        position=Vector2(400, 100),
    )
    effects = EffectSystem(seed=1234, max_particles=MAX_PARTICLES)
    effects.update(0, (event,))
    first_count = len(effects.particles)
    effects.update(0, (event,), reduced=False)
    assert first_count == 9
    assert len(effects.particles) == first_count
    assert len(effects.flashes) == 1

    reduced = EffectSystem(seed=1234)
    reduced.update(0, (event,), reduced=True)
    assert len(reduced.particles) == 3
    assert not reduced.flashes
    reduced.update(1, ())
    assert reduced.particles == []


def test_effect_particle_count_never_exceeds_the_configured_cap() -> None:
    effects = EffectSystem(seed=9, max_particles=MAX_PARTICLES)
    events = tuple(
        make_event(
            EventType.FRUIT_MERGED,
            step,
            entity_ids=(f"left-{step}", f"right-{step}", f"merged-{step}"),
            position=Vector2(400, 100),
        )
        for step in range(30)
    )

    effects.update(0, events)

    assert len(effects.particles) == MAX_PARTICLES


def test_play_scene_queues_edges_until_one_fixed_step_and_pauses_cleanly() -> None:
    physics = FakePhysics()
    session = GameSession(physics, seed=0)
    scene = PlayScene(session)
    frame = InputFrame(edges=(InputEdge(1, InputAction.DROP),))

    assert scene.handle_actions(frame) is None
    scene.simulation_step()
    scene.simulation_step()
    assert session.drop_count == 1

    pause_frame = InputFrame(edges=(InputEdge(2, InputAction.PAUSE),))
    transition = scene.handle_actions(pause_frame)
    assert transition is not None and transition.destination == "pause"
    physics_steps = physics.steps
    scene.simulation_step()
    assert physics.steps == physics_steps
    assert session.round_state is RoundState.PAUSED


def test_play_scene_forwards_domain_snapshot_and_round_metrics_to_canvas() -> None:
    class FakeCanvas:
        def __init__(self) -> None:
            self.snapshot: SessionSnapshot | None = None
            self.metrics: tuple[int, int, float] | None = None

        def set_round_metrics(
            self,
            *,
            best_fruit_level: int,
            watermelons: int,
            duration_seconds: float,
        ) -> None:
            self.metrics = (best_fruit_level, watermelons, duration_seconds)

        def draw_session(
            self, snapshot: SessionSnapshot, events: tuple[DomainEvent, ...]
        ) -> None:
            self.snapshot = snapshot
            assert events == ()

    session = GameSession(FakePhysics(), seed=0)
    scene = PlayScene(session)
    canvas = FakeCanvas()

    scene.draw(canvas)

    assert canvas.snapshot == session.snapshot
    assert canvas.metrics == (0, 0, 0.0)
