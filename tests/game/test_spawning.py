"""Simulation-facing launcher checks with a small PhysicsPort fake."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from suika_elika.contracts import FruitDefinition, InputAction, InputEdge, Pose, Vector2
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.game.randomizer import FruitSequence
from suika_elika.game.spawning import (
    DEFAULT_DROP_INTERVAL,
    DEFAULT_DROP_RATE_BPM,
    AimCircle,
    FruitLauncher,
    LauncherState,
    predict_aim,
)


def test_default_drop_interval_matches_180_drops_per_minute() -> None:
    assert DEFAULT_DROP_RATE_BPM == 180
    assert DEFAULT_DROP_INTERVAL == pytest.approx(60 / 180)


@dataclass(frozen=True, slots=True)
class _Body:
    definition: FruitDefinition
    pose: Pose


class FakePhysics:
    def __init__(self) -> None:
        self.bodies: dict[str, _Body] = {}
        self.blocked_by: tuple[str, ...] = ()
        self.overlap_queries: list[tuple[Vector2, float]] = []

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 | None = None,
        angular_velocity: float = 0.0,
    ) -> None:
        del velocity, angular_velocity
        if entity_id in self.bodies:
            raise ValueError("duplicate body")
        self.bodies[entity_id] = _Body(definition, pose)

    def remove_body(self, entity_id: str) -> None:
        self.bodies.pop(entity_id, None)

    def step(self) -> None:
        pass

    def contacts(self) -> tuple[()]:
        return ()

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        self.overlap_queries.append((center, radius))
        return self.blocked_by

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[()]:
        return ()


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"spawn-{self.value:03d}"


def _launcher(
    *,
    catalog: FruitCatalog | None = None,
    seed: int = 5,
    physics: FakePhysics | None = None,
) -> tuple[FruitLauncher, FruitSequence, FakePhysics]:
    catalog = catalog or load_catalog()
    sequence = FruitSequence(seed, catalog)
    physics = physics or FakePhysics()
    return FruitLauncher(sequence, physics, _Ids()), sequence, physics


def test_preview_is_bodyless_and_only_accepted_drop_advances_sequence() -> None:
    launcher, sequence, physics = _launcher()
    initial_current = sequence.current
    initial_next = sequence.next

    assert launcher.snapshot.current == initial_current
    assert launcher.snapshot.next == initial_next
    assert physics.bodies == {}
    assert launcher.set_launcher_x(10_000) == 800 - initial_current.radius - 4

    result = launcher.handle_drop(InputEdge(1, InputAction.DROP))

    assert result.accepted and result.entity_id == "spawn-001"
    assert sequence.accepted_drops == 1
    assert sequence.current == initial_next
    assert launcher.snapshot.state is LauncherState.READY
    assert physics.bodies[result.entity_id].definition == initial_current
    assert physics.bodies[result.entity_id].pose == Pose(
        Vector2(800 - initial_current.radius - 4, -18)
    )
    assert launcher.snapshot.launcher_x <= 800 - sequence.current.radius - 4


def test_blocked_birth_rejects_without_body_or_sequence_consumption() -> None:
    physics = FakePhysics()
    physics.blocked_by = ("pile-top",)
    launcher, sequence, _ = _launcher(physics=physics)
    current = sequence.current

    result = launcher.handle_drop(InputEdge(10, InputAction.DROP))

    assert not result.accepted
    assert result.reason == "spawn_area_blocked"
    assert launcher.snapshot.state is LauncherState.BLOCKED
    assert launcher.snapshot.blocked_by == ("pile-top",)
    assert sequence.accepted_drops == 0
    assert sequence.current == current
    assert physics.bodies == {}
    center, query_radius = physics.overlap_queries[-1]
    assert center == Vector2(400, -18)
    assert query_radius == pytest.approx(current.radius - 0.5)

    physics.blocked_by = ()
    assert launcher.advance(0) is LauncherState.READY
    assert launcher.handle_drop(InputEdge(11, InputAction.DROP)).accepted
    assert sequence.accepted_drops == 1


def test_fresh_manual_edges_are_immediate_but_replayed_edges_are_ignored() -> None:
    launcher, sequence, _ = _launcher()
    assert launcher.handle_drop(InputEdge(20, InputAction.DROP)).accepted

    assert launcher.handle_drop(InputEdge(21, InputAction.DROP)).accepted
    assert sequence.accepted_drops == 2

    # Replaying the same edge after readiness cannot turn a held button into a drop.
    replayed = launcher.handle_drop(InputEdge(21, InputAction.DROP))
    assert not replayed.accepted and replayed.reason == "duplicate_edge"
    assert launcher.handle_drop(InputEdge(22, InputAction.DROP)).accepted
    assert sequence.accepted_drops == 3


def test_new_presses_never_wait_for_contact_or_timeout() -> None:
    launcher, _, _ = _launcher()
    assert launcher.handle_drop(InputEdge(30, InputAction.DROP)).accepted
    assert launcher.advance(0) is LauncherState.READY

    assert launcher.handle_drop(InputEdge(31, InputAction.DROP)).accepted
    assert launcher.advance(0) is LauncherState.READY


def test_immediate_attempt_still_rejects_an_overlapping_spawn() -> None:
    launcher, sequence, physics = _launcher()
    assert launcher.handle_drop(InputEdge(40, InputAction.DROP)).accepted
    assert launcher.advance(0) is LauncherState.READY

    physics.blocked_by = ("falling-fruit",)
    blocked = launcher.handle_drop(InputEdge(41, InputAction.DROP))

    assert not blocked.accepted and blocked.reason == "spawn_area_blocked"
    assert launcher.snapshot.state is LauncherState.BLOCKED
    assert sequence.accepted_drops == 1


def test_aim_uses_first_vertical_circle_contact_or_floor_only() -> None:
    prediction = predict_aim(
        400,
        14,
        (
            AimCircle("lower", Vector2(420, 200), 20),
            AimCircle("first", Vector2(400, 100), 30),
        ),
    )

    assert prediction.x == 400
    assert prediction.y == pytest.approx(100 - (30 + 14))
    assert prediction.target_entity_id == "first"

    floor = predict_aim(0, 14, ())
    assert floor.x == 18
    assert floor.y == 460 - 14
    assert floor.target_entity_id is None


def test_aim_uses_sum_of_radii_strict_horizontal_intersection_and_skips_above_launch() -> None:
    tangent = predict_aim(
        400,
        14,
        (AimCircle("tangent", Vector2(428, 100), 14),),
    )
    above_launch = predict_aim(
        400,
        14,
        (AimCircle("above", Vector2(400, -80), 80),),
    )

    assert tangent.y == 460 - 14
    assert tangent.target_entity_id is None
    assert above_launch.y == 460 - 14
    assert above_launch.target_entity_id is None


@pytest.mark.parametrize(
    ("fruit_radius", "width", "height", "side_margin"),
    [
        (0, 800, 460, 4),
        (14, 0, 460, 4),
        (14, 800, float("inf"), 4),
        (14, 800, 460, -1),
    ],
)
def test_aim_rejects_invalid_world_or_fruit_dimensions(
    fruit_radius: float,
    width: float,
    height: float,
    side_margin: float,
) -> None:
    with pytest.raises(ValueError):
        predict_aim(
            400,
            fruit_radius,
            (),
            width=width,
            height=height,
            side_margin=side_margin,
        )


def test_launcher_rejects_invalid_delta_and_non_drop_action() -> None:
    launcher, _, _ = _launcher()
    with pytest.raises(ValueError, match="simulation delta"):
        launcher.advance(-0.1)
    with pytest.raises(ValueError, match="DROP"):
        launcher.handle_drop(InputEdge(1, InputAction.CONFIRM))
