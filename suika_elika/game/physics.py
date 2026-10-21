"""Pymunk implementation of the game's fixed-step physics port."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import TypeAlias

import pymunk

from suika_elika.container_geometry import bowl_edge, bowl_outline_points
from suika_elika.contracts import BodySnapshot, ContactSnapshot, FruitDefinition, Pose, Vector2

_ZERO_VELOCITY = Vector2(0.0, 0.0)


@dataclass(frozen=True, slots=True)
class PhysicsConfig:
    """Tunable world dimensions and fixed-step settings for the classic ruleset."""

    width: float = 800.0
    height: float = 460.0
    wall_thickness: float = 12.0
    fixed_dt: float = 1.0 / 120.0
    gravity: Vector2 = Vector2(0.0, 1000.0)
    max_speed: float = 1000.0
    max_angular_speed: float = 10.0
    fruit_friction: float = 1.0
    wall_friction: float = 1.0
    elasticity: float = 0.18
    damping: float = 0.55
    solver_iterations: int = 20
    collision_slop: float = 0.5
    sleep_time_threshold: float = 0.7
    idle_speed_threshold: float = 8.0

    def __post_init__(self) -> None:
        positive = (
            self.width,
            self.height,
            self.wall_thickness,
            self.fixed_dt,
            self.max_speed,
            self.max_angular_speed,
            self.solver_iterations,
        )
        if any(not isfinite(value) or value <= 0 for value in positive):
            raise ValueError("world dimensions, speeds, time step, and iterations must be positive")
        if self.wall_thickness >= min(self.width, self.height):
            raise ValueError("wall thickness must be smaller than the world")
        if any(
            not isfinite(value) or value < 0
            for value in (
                self.fruit_friction,
                self.wall_friction,
                self.elasticity,
                self.sleep_time_threshold,
                self.idle_speed_threshold,
                self.collision_slop,
            )
        ):
            raise ValueError("material and solver settings must be finite and non-negative")
        if not isfinite(self.damping) or not 0 <= self.damping <= 1:
            raise ValueError("damping must be between zero and one")
        if type(self.solver_iterations) is not int:
            raise ValueError("solver_iterations must be an integer")


@dataclass(frozen=True, slots=True)
class _QueuedBody:
    definition: FruitDefinition
    pose: Pose
    velocity: Vector2
    angular_velocity: float


_Mutation: TypeAlias = tuple[str, str, _QueuedBody | None]
_FRUIT_COLLISION_TYPE = 1


class PhysicsWorld:
    """Owns all Pymunk state and returns immutable copies at the domain boundary."""

    def __init__(self, config: PhysicsConfig | None = None) -> None:
        self.config = config or PhysicsConfig()
        self.space = pymunk.Space()
        self.space.gravity = (self.config.gravity.x, self.config.gravity.y)
        self.space.damping = self.config.damping
        self.space.iterations = self.config.solver_iterations
        self.space.collision_slop = self.config.collision_slop
        self.space.sleep_time_threshold = self.config.sleep_time_threshold
        self.space.idle_speed_threshold = self.config.idle_speed_threshold

        self._bodies: dict[str, pymunk.Body] = {}
        self._shapes: dict[str, pymunk.Circle] = {}
        self._entity_by_shape: dict[pymunk.Shape, str] = {}
        self._entity_ids: set[str] = set()
        self._mutations: list[_Mutation] = []
        self._is_stepping = False
        self._contacts: tuple[ContactSnapshot, ...] = ()
        self._step_contacts: list[ContactSnapshot] = []
        self._add_container()
        self.space.on_collision(
            _FRUIT_COLLISION_TYPE,
            _FRUIT_COLLISION_TYPE,
            post_solve=self._on_fruit_contact,
        )

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 = _ZERO_VELOCITY,
        angular_velocity: float = 0.0,
    ) -> None:
        """Create a catalog circle, optionally with a copied initial velocity."""
        if not entity_id:
            raise ValueError("entity_id must not be empty")
        if not isfinite(angular_velocity):
            raise ValueError("angular velocity must be finite")
        if entity_id in self._entity_ids:
            raise ValueError(f"body {entity_id!r} already exists")
        self._entity_ids.add(entity_id)
        self._mutations.append(
            ("add", entity_id, _QueuedBody(definition, pose, velocity, angular_velocity))
        )
        if not self._is_stepping:
            self._apply_mutations()

    def remove_body(self, entity_id: str) -> None:
        """Queue or remove a fruit body, making the ID unavailable immediately."""
        if entity_id not in self._entity_ids:
            return
        self._entity_ids.remove(entity_id)
        self._mutations.append(("remove", entity_id, None))
        if not self._is_stepping:
            self._apply_mutations()

    def step(self) -> None:
        """Advance exactly one fixed step and apply callback mutations afterward."""
        self._apply_mutations()
        self._contacts = ()
        self._step_contacts = []
        self._is_stepping = True
        try:
            self.space.step(self.config.fixed_dt)
        finally:
            self._is_stepping = False
            self._contacts = tuple(self._step_contacts)
            self._step_contacts = []
            self._apply_mutations()

    def contacts(self) -> tuple[ContactSnapshot, ...]:
        """Return copied fruit-to-fruit contacts collected in the most recent step."""
        return self._contacts

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        """Return sorted fruit IDs whose circles touch or overlap the query circle."""
        if not isfinite(radius) or radius <= 0:
            raise ValueError("query radius must be finite and positive")
        query = pymunk.Circle(self.space.static_body, radius, (center.x, center.y))
        found = {
            entity_id
            for info in self.space.shape_query(query)
            if (entity_id := self._entity_by_shape.get(info.shape)) is not None
        }
        return tuple(sorted(found))

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[BodySnapshot, ...]:
        """Copy positions, angles, and velocities for currently present IDs."""
        snapshots: list[BodySnapshot] = []
        for entity_id in entity_ids:
            body = self._bodies.get(entity_id)
            if body is None:
                continue
            snapshots.append(
                BodySnapshot(
                    entity_id=entity_id,
                    pose=Pose(
                        position=Vector2(float(body.position.x), float(body.position.y)),
                        angle=float(body.angle),
                    ),
                    velocity=Vector2(float(body.velocity.x), float(body.velocity.y)),
                )
            )
        return tuple(snapshots)

    def _add_container(self) -> None:
        half = self.config.wall_thickness / 2
        left_x = -half
        right_x = self.config.width + half
        start_y = -half
        edge = bowl_edge(self.config.width, self.config.height)
        outline = bowl_outline_points(self.config.width, self.config.height, edge)
        bottom = outline[2:]
        collision_bottom = tuple((x, y + half) for x, y in bottom)
        walls = (
            pymunk.Segment(
                self.space.static_body,
                (left_x, start_y),
                (left_x, self.config.height - edge + half),
                half,
            ),
            pymunk.Segment(
                self.space.static_body,
                (right_x, start_y),
                (right_x, self.config.height - edge + half),
                half,
            ),
            *(
                pymunk.Segment(self.space.static_body, first, second, half)
                for first, second in zip(
                    collision_bottom, collision_bottom[1:], strict=False
                )
            ),
        )
        for wall in walls:
            wall.friction = self.config.wall_friction
            wall.elasticity = self.config.elasticity
        self.space.add(*walls)

    def _add_body(self, entity_id: str, queued: _QueuedBody) -> None:
        definition = queued.definition
        mass = definition.mass
        moment = 0.5 * mass * definition.radius**2
        body = pymunk.Body(mass, moment)
        body.position = (queued.pose.position.x, queued.pose.position.y)
        body.angle = queued.pose.angle
        body.velocity = (queued.velocity.x, queued.velocity.y)
        body.angular_velocity = queued.angular_velocity
        body.velocity_func = self._limited_velocity
        shape = pymunk.Circle(body, definition.radius)
        shape.friction = self.config.fruit_friction
        shape.elasticity = self.config.elasticity
        shape.collision_type = _FRUIT_COLLISION_TYPE
        self.space.add(body, shape)
        self._bodies[entity_id] = body
        self._shapes[entity_id] = shape
        self._entity_by_shape[shape] = entity_id

    def _remove_body_now(self, entity_id: str) -> None:
        body = self._bodies.pop(entity_id, None)
        shape = self._shapes.pop(entity_id, None)
        if body is None or shape is None:
            return
        self.space.remove(shape, body)
        self._entity_by_shape.pop(shape, None)

    def _apply_mutations(self) -> None:
        mutations, self._mutations = self._mutations, []
        for operation, entity_id, payload in mutations:
            if operation == "remove":
                self._remove_body_now(entity_id)
            elif operation == "add" and payload is not None:
                self._add_body(entity_id, payload)

    def _limited_velocity(
        self, body: pymunk.Body, gravity: pymunk.Vec2d, damping: float, dt: float
    ) -> None:
        pymunk.Body.update_velocity(body, gravity, damping, dt)
        speed = body.velocity.length
        if speed > self.config.max_speed:
            body.velocity = body.velocity * (self.config.max_speed / speed)
        body.angular_velocity = max(
            -self.config.max_angular_speed,
            min(self.config.max_angular_speed, body.angular_velocity),
        )

    def _on_fruit_contact(
        self, arbiter: pymunk.Arbiter, _space: pymunk.Space, _data: object
    ) -> None:
        first_shape, second_shape = arbiter.shapes
        first_id = self._entity_by_shape.get(first_shape)
        second_id = self._entity_by_shape.get(second_shape)
        if first_id is None or second_id is None:
            return
        points = arbiter.contact_point_set.points
        normal = arbiter.normal
        if points:
            # Fruit shapes are circles, so the manifold has a single contact.
            # Avoid building a generator and summing it for every contact.
            point = points[0]
            point_x = (point.point_a.x + point.point_b.x) / 2
            point_y = (point.point_a.y + point.point_b.y) / 2
        else:
            first_body, second_body = arbiter.bodies
            point_x = (first_body.position.x + second_body.position.x) / 2
            point_y = (first_body.position.y + second_body.position.y) / 2
        impulse = arbiter.total_impulse
        self._step_contacts.append(
            ContactSnapshot(
                first_entity_id=first_id,
                second_entity_id=second_id,
                point=Vector2(float(point_x), float(point_y)),
                normal=Vector2(float(normal.x), float(normal.y)),
                impulse=float(hypot(impulse.x, impulse.y)),
            )
        )
