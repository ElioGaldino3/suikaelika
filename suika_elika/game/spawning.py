"""Launcher state, bodyless preview, spawn checks, and static aim prediction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt

from suika_elika.contracts import (
    FruitDefinition,
    InputAction,
    InputEdge,
    PhysicsPort,
    Pose,
    Vector2,
)
from suika_elika.game.randomizer import FruitSequence

DEFAULT_WIDTH = 800.0
DEFAULT_HEIGHT = 460.0
DEFAULT_LAUNCH_Y = -18.0
DEFAULT_SIDE_MARGIN = 4.0
DEFAULT_DROP_RATE_BPM = 180
DEFAULT_DROP_INTERVAL = 60.0 / DEFAULT_DROP_RATE_BPM
DEFAULT_LAUNCH_SPEED = 520.0
DEFAULT_SPAWN_TOLERANCE = 0.5
_TIMER_EPSILON = 1e-9


class LauncherState(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class DropResult:
    """Result of consuming one semantic DROP edge."""

    accepted: bool
    entity_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LauncherSnapshot:
    """Copied state suitable for a session snapshot or a scene."""

    state: LauncherState
    current: FruitDefinition
    next: FruitDefinition
    launcher_x: float
    launch_entity_id: str | None
    blocked_by: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AimCircle:
    """One existing fruit's copied center and collision radius."""

    entity_id: str
    center: Vector2
    radius: float

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("aim circle entity_id must not be empty")
        if not isfinite(self.radius) or self.radius <= 0:
            raise ValueError("aim circle radius must be finite and positive")


@dataclass(frozen=True, slots=True)
class AimPrediction:
    """Static vertical first-contact point; it does not predict final resting place."""

    x: float
    y: float
    target_entity_id: str | None


def predict_aim(
    launcher_x: float,
    fruit_radius: float,
    fruits: tuple[AimCircle, ...],
    *,
    width: float = DEFAULT_WIDTH,
    height: float = DEFAULT_HEIGHT,
    launch_y: float = DEFAULT_LAUNCH_Y,
    side_margin: float = DEFAULT_SIDE_MARGIN,
) -> AimPrediction:
    """Estimate the first vertical circle contact with the pile or container floor."""
    if any(
        not isfinite(value)
        for value in (launcher_x, fruit_radius, width, height, launch_y, side_margin)
    ):
        raise ValueError("aim inputs must be finite")
    if fruit_radius <= 0 or width <= 0 or height <= 0 or side_margin < 0:
        raise ValueError("fruit radius and world dimensions must be positive")
    minimum_x = fruit_radius + side_margin
    maximum_x = width - fruit_radius - side_margin
    if minimum_x > maximum_x:
        raise ValueError("fruit does not fit inside the world width")
    x = max(minimum_x, min(maximum_x, launcher_x))

    first_y = height - fruit_radius
    first_entity_id: str | None = None
    for fruit in sorted(fruits, key=lambda candidate: candidate.entity_id):
        combined_radius = fruit.radius + fruit_radius
        dx = abs(x - fruit.center.x)
        if dx >= combined_radius:
            continue
        contact_y = fruit.center.y - sqrt(combined_radius**2 - dx**2)
        if launch_y <= contact_y < first_y:
            first_y = contact_y
            first_entity_id = fruit.entity_id
    return AimPrediction(x=x, y=first_y, target_entity_id=first_entity_id)


class HeldDropRepeater:
    """Repeat only an explicitly pressed-and-held action on simulation time."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._armed = False
        self._remaining = DEFAULT_DROP_INTERVAL

    def advance(self, delta_seconds: float, *, held: bool, pressed: bool) -> bool:
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("simulation delta must be finite and non-negative")
        if pressed:
            self._armed = held
            self._remaining = DEFAULT_DROP_INTERVAL
            return False
        if not held:
            self.reset()
        if not self._armed:
            return False
        self._remaining -= delta_seconds
        if self._remaining > _TIMER_EPSILON:
            return False
        # One attempt per eligible step, no burst of overdue drops after a stall.
        self._remaining += DEFAULT_DROP_INTERVAL
        if self._remaining <= _TIMER_EPSILON:
            self._remaining = DEFAULT_DROP_INTERVAL
        return True


class FruitLauncher:
    """Own bodyless preview and immediate, overlap-safe launch attempts."""

    def __init__(
        self,
        sequence: FruitSequence,
        physics: PhysicsPort,
        entity_id_factory: Callable[[], str],
        *,
        width: float = DEFAULT_WIDTH,
        height: float = DEFAULT_HEIGHT,
        launch_y: float = DEFAULT_LAUNCH_Y,
        side_margin: float = DEFAULT_SIDE_MARGIN,
        spawn_tolerance: float = DEFAULT_SPAWN_TOLERANCE,
    ) -> None:
        values = (
            width,
            height,
            launch_y,
            side_margin,
            spawn_tolerance,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("launcher configuration must be finite")
        if (
            width <= 0
            or height <= 0
            or side_margin < 0
            or spawn_tolerance < 0
        ):
            raise ValueError("launcher dimensions and timers are invalid")
        self._sequence = sequence
        self._physics = physics
        self._entity_id_factory = entity_id_factory
        self._width = width
        self._height = height
        self._launch_y = launch_y
        self._side_margin = side_margin
        self._spawn_tolerance = spawn_tolerance
        self._launcher_x = width / 2
        self._state = LauncherState.READY
        self._last_edge_sequence = -1
        self._launch_entity_id: str | None = None
        self._blocked_by: tuple[str, ...] = ()

    @property
    def snapshot(self) -> LauncherSnapshot:
        return LauncherSnapshot(
            state=self._state,
            current=self._sequence.current,
            next=self._sequence.next,
            launcher_x=self._launcher_x,
            launch_entity_id=self._launch_entity_id,
            blocked_by=self._blocked_by,
        )

    @property
    def launcher_x(self) -> float:
        return self._launcher_x

    def set_launcher_x(self, value: float) -> float:
        """Move the preview while falling bodies continue to simulate."""
        if not isfinite(value):
            raise ValueError("launcher x must be finite")
        radius = self._sequence.current.radius
        minimum_x = radius + self._side_margin
        maximum_x = self._width - radius - self._side_margin
        if minimum_x > maximum_x:
            raise ValueError("current fruit does not fit inside the world width")
        self._launcher_x = max(minimum_x, min(maximum_x, value))
        return self._launcher_x

    def handle_drop(self, edge: InputEdge) -> DropResult:
        """Consume one fresh DROP edge, discarding it whenever release is invalid."""
        if edge.action is not InputAction.DROP:
            raise ValueError("launcher accepts only DROP input edges")
        if edge.sequence <= self._last_edge_sequence:
            return DropResult(False, reason="duplicate_edge")
        self._last_edge_sequence = edge.sequence
        return self.try_drop()

    def try_drop(self) -> DropResult:
        """Try a scheduled repetition or a fresh press without artificial cooldown."""
        definition = self._sequence.current
        self.set_launcher_x(self._launcher_x)
        spawn_center = Vector2(self._launcher_x, self._launch_y)
        query_radius = max(0.01, definition.radius - self._spawn_tolerance)
        blocked_by = self._physics.overlaps(spawn_center, query_radius)
        if blocked_by:
            self._state = LauncherState.BLOCKED
            self._blocked_by = blocked_by
            return DropResult(False, reason="spawn_area_blocked")

        entity_id = self._entity_id_factory()
        if not entity_id:
            raise ValueError("entity id factory must return a non-empty identifier")
        self._physics.create_body(
            entity_id,
            definition,
            Pose(spawn_center),
            velocity=Vector2(0.0, DEFAULT_LAUNCH_SPEED),
        )
        self._sequence.try_consume_drop(accepted=True)
        self._launch_entity_id = entity_id
        self._blocked_by = ()
        self._state = LauncherState.READY
        # Clamp again because the newly revealed preview may be a different size.
        self.set_launcher_x(self._launcher_x)
        return DropResult(True, entity_id=entity_id)

    def advance(
        self,
        delta_seconds: float,
    ) -> LauncherState:
        """Refresh a blocked mouth; only geometry can delay a manual launch."""
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("simulation delta must be finite and non-negative")

        if self._state is LauncherState.BLOCKED:
            definition = self._sequence.current
            blockers = self._physics.overlaps(
                Vector2(self._launcher_x, self._launch_y),
                max(0.01, definition.radius - self._spawn_tolerance),
            )
            self._blocked_by = blockers
            if not blockers:
                self._state = LauncherState.READY
            return self._state

        return self._state


__all__ = [
    "AimCircle",
    "AimPrediction",
    "DropResult",
    "FruitLauncher",
    "HeldDropRepeater",
    "LauncherSnapshot",
    "LauncherState",
    "predict_aim",
]
