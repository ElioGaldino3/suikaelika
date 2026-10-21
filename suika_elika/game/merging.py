"""Post-step fruit merge detection and transactional world mutations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import atan2, cos, floor, hypot, isfinite, sin, sqrt

from suika_elika.contracts import (
    ContactSnapshot,
    DomainEvent,
    EventType,
    FruitDefinition,
    PhysicsPort,
    Pose,
    Vector2,
    make_event,
)
from suika_elika.game.catalog import FruitCatalog

_MERGE_DAMPING = 0.75
_ANGULAR_DAMPING = 0.5
_POSITION_SEARCH_LIMIT = 12.0
_MERGE_CONTACT_TOLERANCE = 1.5
_DIRECTIONS: tuple[tuple[float, float], ...] = (
    (0.0, -1.0),
    (-1.0, 0.0),
    (1.0, 0.0),
    (0.0, 1.0),
    (-sqrt(0.5), -sqrt(0.5)),
    (sqrt(0.5), -sqrt(0.5)),
    (-sqrt(0.5), sqrt(0.5)),
    (sqrt(0.5), sqrt(0.5)),
)


@dataclass(frozen=True, slots=True)
class MergeFruit:
    """Simulation values needed to prepare one merge without engine objects."""

    entity_id: str
    definition: FruitDefinition
    pose: Pose
    velocity: Vector2
    angular_velocity: float = 0.0
    danger_eligible: bool = False
    danger_seconds: float = 0.0
    protection_age_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("merge fruit entity_id must not be empty")
        if not isfinite(self.angular_velocity):
            raise ValueError("merge fruit angular velocity must be finite")
        if not isfinite(self.danger_seconds) or self.danger_seconds < 0:
            raise ValueError("danger seconds must be finite and non-negative")
        if self.protection_age_seconds is not None and (
            not isfinite(self.protection_age_seconds) or self.protection_age_seconds < 0
        ):
            raise ValueError("protection age must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class MergeResolution:
    """One immutable post-step result for GameSession to publish and score."""

    fruits: tuple[MergeFruit, ...]
    merged_pairs: tuple[tuple[str, str], ...]
    events: tuple[DomainEvent, ...]
    score_delta: int


class MergeSystem:
    """Choose non-overlapping contact pairs and apply mutations after a physics step.

    Call ``resolve`` after ``PhysicsPort.step`` returns. The method snapshots all
    candidate values before touching the port, reserves parents deterministically,
    then removes and creates bodies in a second phase. No engine contact callback
    object is retained or accepted by this boundary.
    """

    def __init__(
        self,
        catalog: FruitCatalog,
        physics: PhysicsPort,
        entity_id_factory: Callable[[], str],
        *,
        width: float = 800.0,
        height: float = 460.0,
        max_speed: float = 1000.0,
        max_angular_speed: float = 10.0,
    ) -> None:
        if any(
            not isfinite(value) or value <= 0
            for value in (width, height, max_speed, max_angular_speed)
        ):
            raise ValueError("world bounds and velocity limits must be finite and positive")
        self._catalog = catalog
        self._physics = physics
        self._entity_id_factory = entity_id_factory
        self._width = width
        self._height = height
        self._max_speed = max_speed
        self._max_angular_speed = max_angular_speed
        self._issued_ids: set[str] = set()

    def resolve(
        self,
        fruits: tuple[MergeFruit, ...],
        *,
        step_index: int,
        contacts: tuple[ContactSnapshot, ...] | None = None,
    ) -> MergeResolution:
        """Confirm every independent eligible pair reported for this step."""
        if step_index < 0:
            raise ValueError("step_index must be non-negative")
        by_id = {fruit.entity_id: fruit for fruit in fruits}
        if len(by_id) != len(fruits):
            raise ValueError("active fruit entity IDs must be unique")

        snapshots = contacts if contacts is not None else self._physics.contacts()
        candidate_pairs = {
            tuple(sorted((contact.first_entity_id, contact.second_entity_id)))
            for contact in snapshots
            if contact.first_entity_id != contact.second_entity_id
        }
        candidate_pairs.update(self._nearby_equal_fruit_pairs(fruits))
        pair_keys = sorted(candidate_pairs)
        reserved: set[str] = set()
        plans: list[tuple[MergeFruit, MergeFruit, FruitDefinition | None]] = []
        for first_id, second_id in pair_keys:
            first = by_id.get(first_id)
            second = by_id.get(second_id)
            if first is None or second is None or first_id in reserved or second_id in reserved:
                continue
            if first.definition.fruit_id != second.definition.fruit_id:
                continue
            if first.definition.level != second.definition.level:
                continue
            result_definition = self._result_definition(first.definition)
            reserved.update((first_id, second_id))
            plans.append((first, second, result_definition))

        if not plans:
            return MergeResolution(
                fruits=tuple(sorted(fruits, key=lambda fruit: fruit.entity_id)),
                merged_pairs=(),
                events=(),
                score_delta=0,
            )

        consumed = {fruit.entity_id for first, second, _ in plans for fruit in (first, second)}
        survivors = [fruit for fruit in fruits if fruit.entity_id not in consumed]
        active_after_consumption = {
            entity_id: fruit for entity_id, fruit in by_id.items() if entity_id not in consumed
        }
        created: list[MergeFruit] = []
        merge_events: list[DomainEvent] = []
        merged_pairs: list[tuple[str, str]] = []
        score_delta = 0

        for first, second, definition in plans:
            parents = tuple(sorted((first, second), key=lambda fruit: fruit.entity_id))
            first, second = parents
            merged_pairs.append((first.entity_id, second.entity_id))
            center = self._center_of_mass(first, second)
            if definition is None:
                points = 100
                merge_events.append(
                    make_event(
                        EventType.FRUIT_MERGED,
                        step_index,
                        entity_ids=(first.entity_id, second.entity_id),
                        position=center,
                        payload=(
                            ("fruit_id", "double_watermelon"),
                            ("points", points),
                            ("double_watermelon", True),
                        ),
                    )
                )
            else:
                child_id = self._new_id(by_id, created)
                child_pose = self._child_pose(
                    first,
                    second,
                    definition.radius,
                    center,
                    active_after_consumption,
                    consumed,
                )
                child_velocity = self._child_velocity(first, second)
                child_angular_velocity = self._child_angular_velocity(first, second)
                protection_age = (
                    max(first.protection_age_seconds, second.protection_age_seconds)
                    if first.protection_age_seconds is not None
                    and second.protection_age_seconds is not None
                    else None
                )
                child = MergeFruit(
                    entity_id=child_id,
                    definition=definition,
                    pose=child_pose,
                    velocity=child_velocity,
                    angular_velocity=child_angular_velocity,
                    danger_eligible=first.danger_eligible or second.danger_eligible,
                    danger_seconds=max(first.danger_seconds, second.danger_seconds),
                    protection_age_seconds=protection_age,
                )
                created.append(child)
                center = child_pose.position
                points = definition.points_on_spawn
                merge_events.append(
                    make_event(
                        EventType.FRUIT_MERGED,
                        step_index,
                        entity_ids=(first.entity_id, second.entity_id, child_id),
                        position=center,
                        payload=(
                            ("fruit_id", definition.fruit_id),
                            ("level", definition.level),
                            ("points", points),
                        ),
                    )
                )
            score_delta += points

        # All merge candidates and replacement values are computed before world edits.
        for entity_id in sorted(consumed):
            self._physics.remove_body(entity_id)
        for child in created:
            self._physics.create_body(
                child.entity_id,
                child.definition,
                child.pose,
                velocity=child.velocity,
                angular_velocity=child.angular_velocity,
            )

        events = list(merge_events)
        if score_delta:
            events.append(
                make_event(
                    EventType.SCORE_CHANGED,
                    step_index,
                    payload=(("delta", score_delta),),
                )
            )
        return MergeResolution(
            fruits=tuple(sorted((*survivors, *created), key=lambda fruit: fruit.entity_id)),
            merged_pairs=tuple(merged_pairs),
            events=tuple(events),
            score_delta=score_delta,
        )

    @staticmethod
    def _nearby_equal_fruit_pairs(
        fruits: tuple[MergeFruit, ...],
    ) -> set[tuple[str, str]]:
        """Find same-level circles that touch, even when Pymunk emitted no event.

        Pymunk's ``post_solve`` callback is omitted for sleeping contacts. A
        level-specific spatial grid keeps this fallback proportional to nearby
        fruit counts instead of comparing every fruit with every other fruit.
        """
        by_level: dict[int, list[MergeFruit]] = {}
        for fruit in fruits:
            by_level.setdefault(fruit.definition.level, []).append(fruit)

        pairs: set[tuple[str, str]] = set()
        for level_fruits in by_level.values():
            cell_size = (
                2 * max(fruit.definition.radius for fruit in level_fruits)
                + _MERGE_CONTACT_TOLERANCE
            )
            cells: dict[tuple[int, int], list[MergeFruit]] = {}
            for fruit in level_fruits:
                x, y = fruit.pose.position.x, fruit.pose.position.y
                cell = (floor(x / cell_size), floor(y / cell_size))
                for cell_x in range(cell[0] - 1, cell[0] + 2):
                    for cell_y in range(cell[1] - 1, cell[1] + 2):
                        for other in cells.get((cell_x, cell_y), ()):
                            if fruit.definition.fruit_id != other.definition.fruit_id:
                                continue
                            reach = (
                                fruit.definition.radius
                                + other.definition.radius
                                + _MERGE_CONTACT_TOLERANCE
                            )
                            dx = x - other.pose.position.x
                            dy = y - other.pose.position.y
                            if dx * dx + dy * dy <= reach * reach:
                                pairs.add(
                                    (
                                        min(other.entity_id, fruit.entity_id),
                                        max(other.entity_id, fruit.entity_id),
                                    )
                                )
                cells.setdefault(cell, []).append(fruit)
        return pairs

    def _result_definition(self, definition: FruitDefinition) -> FruitDefinition | None:
        if definition.level == 11:
            return None
        return next(
            entry.definition
            for entry in self._catalog.entries
            if entry.level == definition.level + 1
        )

    @staticmethod
    def _center_of_mass(first: MergeFruit, second: MergeFruit) -> Vector2:
        total_mass = first.definition.mass + second.definition.mass
        return Vector2(
            (
                first.pose.position.x * first.definition.mass
                + second.pose.position.x * second.definition.mass
            )
            / total_mass,
            (
                first.pose.position.y * first.definition.mass
                + second.pose.position.y * second.definition.mass
            )
            / total_mass,
        )

    def _child_pose(
        self,
        first: MergeFruit,
        second: MergeFruit,
        radius: float,
        center: Vector2,
        active: dict[str, MergeFruit],
        removed_ids: set[str],
    ) -> Pose:
        angle = atan2(
            sin(first.pose.angle) + sin(second.pose.angle),
            cos(first.pose.angle) + cos(second.pose.angle),
        )
        initial = self._constrain(center, radius)
        ignored = removed_ids
        if self._is_clear(initial, radius, ignored):
            return Pose(initial, angle)

        candidates: list[Vector2] = []
        seen: set[tuple[float, float]] = set()
        for distance in range(1, int(_POSITION_SEARCH_LIMIT) + 1):
            for dx, dy in _DIRECTIONS:
                candidate = self._constrain(
                    Vector2(center.x + dx * distance, center.y + dy * distance), radius
                )
                key = (candidate.x, candidate.y)
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
        for candidate in candidates:
            if self._is_clear(candidate, radius, ignored):
                return Pose(candidate, angle)

        best = min(
            candidates,
            key=lambda candidate: (
                self._penetration(candidate, radius, active, ignored),
                hypot(candidate.x - center.x, candidate.y - center.y),
                candidate.y,
                candidate.x,
            ),
        )
        return Pose(best, angle)

    def _constrain(self, point: Vector2, radius: float) -> Vector2:
        return Vector2(
            min(self._width - radius, max(radius, point.x)),
            min(self._height - radius, point.y),
        )

    def _is_clear(self, center: Vector2, radius: float, ignored: set[str]) -> bool:
        return not (set(self._physics.overlaps(center, radius)) - ignored)

    @staticmethod
    def _penetration(
        center: Vector2,
        radius: float,
        active: dict[str, MergeFruit],
        ignored: set[str],
    ) -> float:
        total = 0.0
        for entity_id, fruit in active.items():
            if entity_id in ignored:
                continue
            dx = center.x - fruit.pose.position.x
            dy = center.y - fruit.pose.position.y
            total += max(0.0, radius + fruit.definition.radius - hypot(dx, dy))
        return total

    def _child_velocity(self, first: MergeFruit, second: MergeFruit) -> Vector2:
        mass_first = first.definition.mass
        mass_second = second.definition.mass
        total = mass_first + mass_second
        x = (
            _MERGE_DAMPING
            * (mass_first * first.velocity.x + mass_second * second.velocity.x)
            / total
        )
        y = (
            _MERGE_DAMPING
            * (mass_first * first.velocity.y + mass_second * second.velocity.y)
            / total
        )
        speed = hypot(x, y)
        if speed > self._max_speed:
            scale = self._max_speed / speed
            x *= scale
            y *= scale
        return Vector2(x, y)

    def _child_angular_velocity(self, first: MergeFruit, second: MergeFruit) -> float:
        value = _ANGULAR_DAMPING * (first.angular_velocity + second.angular_velocity) / 2
        return min(self._max_angular_speed, max(-self._max_angular_speed, value))

    def _new_id(self, active: dict[str, MergeFruit], created: list[MergeFruit]) -> str:
        entity_id = self._entity_id_factory()
        known = set(active) | {fruit.entity_id for fruit in created} | self._issued_ids
        if not entity_id or entity_id in known:
            raise ValueError("entity id factory must return a new non-empty identifier")
        self._issued_ids.add(entity_id)
        return entity_id


__all__ = ["MergeFruit", "MergeResolution", "MergeSystem"]
