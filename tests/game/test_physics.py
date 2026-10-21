"""Scenario checks for the Pymunk physics adapter."""

from __future__ import annotations

from math import isclose

import pymunk
import pytest

from suika_elika.contracts import FruitDefinition, Pose, Vector2
from suika_elika.game.catalog import load_catalog
from suika_elika.game.physics import PhysicsConfig, PhysicsWorld


def _fruit(radius: float = 14.0) -> FruitDefinition:
    return FruitDefinition(
        fruit_id="test-fruit",
        level=1,
        radius=radius,
        mass=(radius / 14) ** 2,
        points_on_spawn=0,
        visual_key="test-fruit",
    )


def _advance(world: PhysicsWorld, seconds: float) -> None:
    for _ in range(round(seconds / world.config.fixed_dt)):
        world.step()


def test_default_world_uses_classic_fixed_step_and_empty_open_top_container() -> None:
    world = PhysicsWorld()

    assert world.config.fixed_dt == pytest.approx(1 / 120)
    assert world.space.gravity == (0, 1000)
    assert len(world.space.static_body.shapes) == 3
    assert len(world.space.shapes) == 3
    assert all(isinstance(shape, pymunk.Segment) for shape in world.space.shapes)


def test_fruit_falls_and_keeps_catalog_mass_and_solid_disk_moment() -> None:
    world = PhysicsWorld()
    definition = load_catalog().get("strawberry").definition
    world.create_body("falling", definition, Pose(Vector2(400, 100)))
    body = world._bodies["falling"]

    assert body.mass == pytest.approx(definition.mass)
    assert body.moment == pytest.approx(0.5 * definition.mass * definition.radius**2)
    _advance(world, 0.25)

    snapshot = world.poses(("falling",))[0]
    assert snapshot.pose.position.y > 100
    assert snapshot.velocity.y > 0


def test_adjusted_catalog_radius_reaches_the_pymunk_circle_shape() -> None:
    catalog = load_catalog().with_hitbox_scales((("apple", 1.25),))
    world = PhysicsWorld()
    world.create_body(
        "apple",
        catalog.get("apple").definition,
        Pose(Vector2(400, 100)),
    )

    assert world._shapes["apple"].radius == pytest.approx(45)


def test_body_accepts_initial_linear_and_angular_velocity_through_public_api() -> None:
    world = PhysicsWorld()
    world.create_body(
        "moving",
        _fruit(),
        Pose(Vector2(300, 100)),
        velocity=Vector2(12.5, -4.0),
        angular_velocity=1.25,
    )

    snapshot = world.poses(("moving",))[0]
    assert snapshot.velocity == Vector2(12.5, -4.0)
    assert world._bodies["moving"].angular_velocity == pytest.approx(1.25)


def test_body_rejects_non_finite_initial_angular_velocity() -> None:
    world = PhysicsWorld()
    with pytest.raises(ValueError, match="angular velocity"):
        world.create_body(
            "invalid",
            _fruit(),
            Pose(Vector2(300, 100)),
            angular_velocity=float("nan"),
        )


@pytest.mark.parametrize("x", [2.0, 798.0])
def test_side_walls_keep_fruit_inside(x: float) -> None:
    world = PhysicsWorld()
    world.create_body("wall", _fruit(), Pose(Vector2(x, 300)))
    _advance(world, 0.6)

    snapshot = world.poses(("wall",))[0]
    assert snapshot.pose.position.x >= 14 - 1
    assert snapshot.pose.position.x <= 800 - 14 + 1
    assert snapshot.pose.position.y > 300


def test_floor_stops_fruit_and_allows_it_to_rest() -> None:
    world = PhysicsWorld()
    world.create_body("resting", _fruit(), Pose(Vector2(400, 400)))
    _advance(world, 5)

    snapshot = world.poses(("resting",))[0]
    assert snapshot.pose.position.y == pytest.approx(460 - 20, abs=1.5)
    assert abs(snapshot.velocity.y) < 8


def test_open_top_has_no_ceiling_collision() -> None:
    world = PhysicsWorld()
    world.create_body("upward", _fruit(), Pose(Vector2(400, 5)))
    world._bodies["upward"].velocity = (0, -200)
    _advance(world, 0.1)

    assert world.poses(("upward",))[0].pose.position.y < -5


def test_basket_floor_is_flat_and_sides_are_vertical() -> None:
    world = PhysicsWorld()
    floors = tuple(
        shape
        for shape in world.space.shapes
        if isinstance(shape, pymunk.Segment) and shape.a.x != shape.b.x
    )

    assert len(floors) == 1
    assert isclose(floors[0].a.y, floors[0].b.y, abs_tol=1e-9)

    sides = tuple(
        shape
        for shape in world.space.shapes
        if isinstance(shape, pymunk.Segment) and shape.a.x == shape.b.x
    )
    assert len(sides) == 2


def test_default_materials_reduce_bounce_and_residual_motion() -> None:
    config = PhysicsConfig()

    assert config.fruit_friction == 1.0
    assert config.wall_friction == 1.0
    assert config.elasticity < 0.2
    assert config.damping < 0.6


def test_velocity_and_angular_velocity_are_clamped() -> None:
    world = PhysicsWorld()
    world.create_body("fast", _fruit(), Pose(Vector2(400, 100)))
    body = world._bodies["fast"]
    body.velocity = (2000, 0)
    body.angular_velocity = 50
    world.step()

    snapshot = world.poses(("fast",))[0]
    assert isclose(snapshot.velocity.x**2 + snapshot.velocity.y**2, 1000**2, abs_tol=1e-3)
    assert isclose(body.angular_velocity, 10, abs_tol=1e-6)


def test_contacts_and_overlap_results_are_copied_and_sorted() -> None:
    world = PhysicsWorld()
    world.create_body("b", _fruit(), Pose(Vector2(300, 100)))
    world.create_body("a", _fruit(), Pose(Vector2(325, 100)))
    world._bodies["b"].velocity = (150, 0)
    world.step()

    contacts = world.contacts()
    assert contacts
    contact = contacts[0]
    assert {contact.first_entity_id, contact.second_entity_id} == {"a", "b"}
    assert isinstance(contact.point, Vector2)
    assert isinstance(contact.normal, Vector2)
    assert contact.impulse >= 0
    assert world.overlaps(Vector2(312.5, 100), 30) == ("a", "b")


def test_mutations_requested_inside_step_apply_after_step() -> None:
    world = PhysicsWorld()
    world.create_body("first", _fruit(), Pose(Vector2(100, 100)))
    original_velocity_func = world._bodies["first"].velocity_func

    def add_during_step(
        body: pymunk.Body, gravity: pymunk.Vec2d, damping: float, dt: float
    ) -> None:
        assert original_velocity_func is not None
        original_velocity_func(body, gravity, damping, dt)
        world.create_body("second", _fruit(), Pose(Vector2(200, 100)))

    world._bodies["first"].velocity_func = add_during_step
    world.step()

    assert tuple(item.entity_id for item in world.poses(("first", "second"))) == (
        "first",
        "second",
    )
    assert len(world._mutations) == 0


def test_remove_is_idempotent_and_unknown_poses_are_omitted() -> None:
    world = PhysicsWorld()
    world.create_body("one", _fruit(), Pose(Vector2(200, 100)))
    world.remove_body("one")
    world.remove_body("one")

    assert world.poses(("one", "missing")) == ()
    assert world.overlaps(Vector2(200, 100), 20) == ()


def test_config_rejects_invalid_fixed_step() -> None:
    with pytest.raises(ValueError, match="positive"):
        PhysicsConfig(fixed_dt=0)
