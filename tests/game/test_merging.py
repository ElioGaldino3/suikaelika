"""Simulated world tests for deterministic post-step merge transactions."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, pi

from suika_elika.contracts import ContactSnapshot, EventType, FruitDefinition, Pose, Vector2
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.game.merging import MergeFruit, MergeSystem


@dataclass(frozen=True)
class _SimulatedBody:
    definition: FruitDefinition
    pose: Pose
    velocity: Vector2
    angular_velocity: float


class SimulatedPhysics:
    """Small PhysicsPort fake; no physical hardware or Pymunk callbacks used."""

    def __init__(self) -> None:
        self.bodies: dict[str, _SimulatedBody] = {}
        self.current_contacts: tuple[ContactSnapshot, ...] = ()

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 | None = None,
        angular_velocity: float = 0.0,
    ) -> None:
        if entity_id in self.bodies:
            raise ValueError("duplicate entity ID")
        self.bodies[entity_id] = _SimulatedBody(
            definition,
            pose,
            velocity if velocity is not None else Vector2(0.0, 0.0),
            angular_velocity,
        )

    def remove_body(self, entity_id: str) -> None:
        self.bodies.pop(entity_id, None)

    def step(self) -> None:
        pass

    def contacts(self) -> tuple[ContactSnapshot, ...]:
        return self.current_contacts

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        return tuple(
            sorted(
                entity_id
                for entity_id, body in self.bodies.items()
                if hypot(
                    center.x - body.pose.position.x,
                    center.y - body.pose.position.y,
                )
                <= radius + body.definition.radius
            )
        )

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[()]:
        return ()


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"merge-{self.value:03d}"


def _fruit(
    catalog: FruitCatalog,
    entity_id: str,
    fruit_id: str,
    x: float,
    y: float,
    *,
    vx: float = 0.0,
    vy: float = 0.0,
    angle: float = 0.0,
    angular_velocity: float = 0.0,
    danger_eligible: bool = False,
    danger_seconds: float = 0.0,
    protection_age_seconds: float | None = None,
) -> MergeFruit:
    entry = catalog.get(fruit_id)
    return MergeFruit(
        entity_id=entity_id,
        definition=entry.definition,
        pose=Pose(Vector2(x, y), angle),
        velocity=Vector2(vx, vy),
        angular_velocity=angular_velocity,
        danger_eligible=danger_eligible,
        danger_seconds=danger_seconds,
        protection_age_seconds=protection_age_seconds,
    )


def _world(fruits: tuple[MergeFruit, ...]) -> SimulatedPhysics:
    world = SimulatedPhysics()
    for fruit in fruits:
        world.create_body(
            fruit.entity_id,
            fruit.definition,
            fruit.pose,
            velocity=fruit.velocity,
            angular_velocity=fruit.angular_velocity,
        )
    return world


def _contact(first: str, second: str) -> ContactSnapshot:
    return ContactSnapshot(
        first_entity_id=first,
        second_entity_id=second,
        point=Vector2(0.0, 0.0),
        normal=Vector2(1.0, 0.0),
        impulse=1.0,
    )


def _system(world: SimulatedPhysics) -> MergeSystem:
    return MergeSystem(load_catalog(), world, _Ids())


def test_three_equal_contacts_reserve_one_pair_and_ignore_duplicates() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "a", "cherry", 100, 100),
        _fruit(catalog, "b", "cherry", 120, 100),
        _fruit(catalog, "c", "cherry", 140, 100),
    )
    world = _world(fruits)
    system = _system(world)

    result = system.resolve(
        fruits,
        step_index=4,
        contacts=(_contact("c", "a"), _contact("a", "c"), _contact("a", "b")),
    )

    assert result.merged_pairs == (("a", "b"),)
    assert {fruit.entity_id for fruit in result.fruits} == {"c", "merge-001"}
    assert set(world.bodies) == {"c", "merge-001"}
    assert result.score_delta == catalog.get("strawberry").definition.points_on_spawn
    merge_event = next(
        event for event in result.events if event.event_type is EventType.FRUIT_MERGED
    )
    assert merge_event.step_index == 4
    assert merge_event.entity_ids == ("a", "b", "merge-001")
    assert all(not hasattr(event, "arbiter") for event in result.events)


def test_independent_pairs_merge_in_one_step_with_mass_weighted_damped_velocity() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "a", "cherry", 100, 100, vx=10, vy=20, angle=pi - 0.1, angular_velocity=4),
        _fruit(catalog, "b", "cherry", 120, 100, vx=30, vy=40, angle=-pi + 0.1, angular_velocity=8),
        _fruit(catalog, "c", "lemon", 300, 100, vx=-20, vy=0, angular_velocity=-4),
        _fruit(catalog, "d", "lemon", 340, 100, vx=20, vy=20, angular_velocity=0),
    )
    world = _world(fruits)

    result = MergeSystem(catalog, world, _Ids()).resolve(
        fruits,
        step_index=9,
        contacts=(_contact("d", "c"), _contact("b", "a")),
    )

    assert result.merged_pairs == (("a", "b"), ("c", "d"))
    assert len(result.fruits) == 2
    by_id = {fruit.entity_id: fruit for fruit in result.fruits}
    cherry_child = by_id["merge-001"]
    assert cherry_child.definition.fruit_id == "strawberry"
    assert cherry_child.velocity == Vector2(15, 22.5)
    assert abs(abs(cherry_child.pose.angle) - pi) < 0.01
    assert cherry_child.angular_velocity == 3
    assert by_id["merge-002"].definition.fruit_id == "apple"
    assert result.score_delta == (
        catalog.get("strawberry").definition.points_on_spawn
        + catalog.get("apple").definition.points_on_spawn
    )
    merge_events = [event for event in result.events if event.event_type is EventType.FRUIT_MERGED]
    score_events = [event for event in result.events if event.event_type is EventType.SCORE_CHANGED]
    assert len(merge_events) == 2
    assert len(score_events) == 1


def test_child_inherits_danger_and_oldest_protection_age_when_both_protected() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(
            catalog,
            "old",
            "cherry",
            100,
            100,
            danger_eligible=True,
            danger_seconds=0.4,
            protection_age_seconds=0.8,
        ),
        _fruit(
            catalog,
            "new",
            "cherry",
            120,
            100,
            danger_seconds=0.1,
            protection_age_seconds=0.3,
        ),
    )
    world = _world(fruits)

    result = MergeSystem(catalog, world, _Ids()).resolve(
        fruits, step_index=10, contacts=(_contact("old", "new"),)
    )

    child = result.fruits[0]
    assert child.danger_eligible
    assert child.danger_seconds == 0.4
    assert child.protection_age_seconds == 0.8
    assert world.bodies[child.entity_id].velocity == Vector2(0.0, 0.0)
    assert world.bodies[child.entity_id].angular_velocity == 0.0


def test_position_correction_uses_local_candidates_and_keeps_child_within_bowl() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "a", "cherry", 100, 100),
        _fruit(catalog, "b", "cherry", 120, 100),
        _fruit(catalog, "blocker", "strawberry", 110, 100),
    )
    world = _world(fruits)

    result = MergeSystem(catalog, world, _Ids()).resolve(
        fruits, step_index=11, contacts=(_contact("a", "b"),)
    )

    child = next(fruit for fruit in result.fruits if fruit.entity_id.startswith("merge-"))
    assert 0 <= child.pose.position.x <= 800
    assert child.pose.position.y <= 460 - child.definition.radius
    assert hypot(child.pose.position.x - 110, child.pose.position.y - 100) > 0
    assert hypot(child.pose.position.x - 110, child.pose.position.y - 100) <= 12.1


def test_same_contact_on_later_step_does_not_award_points_twice_and_chain_uses_child() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "a", "cherry", 200, 100),
        _fruit(catalog, "b", "cherry", 220, 100),
        _fruit(catalog, "c", "strawberry", 240, 100),
    )
    world = _world(fruits)
    system = _system(world)

    first = system.resolve(fruits, step_index=1, contacts=(_contact("a", "b"),))
    repeated = system.resolve(first.fruits, step_index=2, contacts=(_contact("a", "b"),))
    assert repeated.score_delta == 0
    assert repeated.merged_pairs == ()

    child: MergeFruit = next(fruit for fruit in first.fruits if fruit.entity_id == "merge-001")
    chain = system.resolve(
        first.fruits,
        step_index=3,
        contacts=(_contact(child.entity_id, "c"),),
    )
    assert chain.merged_pairs == (("c", "merge-001"),)
    chain_child: MergeFruit = next(
        fruit for fruit in chain.fruits if fruit.entity_id == "merge-002"
    )
    assert chain_child.definition.fruit_id == "grape"
    assert chain.score_delta == catalog.get("grape").definition.points_on_spawn


def test_double_watermelon_removes_both_without_level_twelve_child() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "melon-a", "watermelon", 300, 300),
        _fruit(catalog, "melon-b", "watermelon", 500, 300),
    )
    world = _world(fruits)

    result = MergeSystem(catalog, world, _Ids()).resolve(
        fruits, step_index=23, contacts=(_contact("melon-b", "melon-a"),)
    )

    assert result.fruits == ()
    assert world.bodies == {}
    assert result.score_delta == 100
    assert result.merged_pairs == (("melon-a", "melon-b"),)
    assert result.events[0].payload == (
        ("fruit_id", "double_watermelon"),
        ("points", 100),
        ("double_watermelon", True),
    )


def test_nonmatching_contacts_and_invalid_active_ids_do_not_mutate_world() -> None:
    catalog = load_catalog()
    fruits = (
        _fruit(catalog, "cherry", "cherry", 100, 100),
        _fruit(catalog, "berry", "strawberry", 120, 100),
    )
    world = _world(fruits)
    system = _system(world)

    result = system.resolve(fruits, step_index=2, contacts=(_contact("cherry", "berry"),))

    assert result.merged_pairs == ()
    assert result.score_delta == 0
    assert result.events == ()
    assert set(world.bodies) == {"cherry", "berry"}
