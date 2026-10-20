"""Protocols at the boundaries between the domain and concrete adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .events import DomainEvent
from .input import InputFrame
from .models import FruitDefinition, Pose, SessionSnapshot, Vector2


@dataclass(frozen=True, slots=True)
class ContactSnapshot:
    """Copied contact result; no physics arbiter or shape crosses this boundary."""

    first_entity_id: str
    second_entity_id: str
    point: Vector2
    normal: Vector2
    impulse: float


@dataclass(frozen=True, slots=True)
class BodySnapshot:
    entity_id: str
    pose: Pose
    velocity: Vector2


class PhysicsPort(Protocol):
    """Operations owned by the physics adapter; only it mutates its world."""

    def create_body(self, entity_id: str, definition: FruitDefinition, pose: Pose) -> None: ...

    def remove_body(self, entity_id: str) -> None: ...

    def step(self) -> None: ...

    def contacts(self) -> tuple[ContactSnapshot, ...]: ...

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]: ...

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[BodySnapshot, ...]: ...


class AudioPort(Protocol):
    """Presentation-only event consumer with a silent implementation allowed."""

    def consume(self, events: tuple[DomainEvent, ...]) -> None: ...

    def set_gains(self, *, master: float, effects: float, music: float) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SettingsData:
    """Persistable user preferences with no live device or mixer references."""

    master_gain: float = 0.8
    effects_gain: float = 0.75
    music_gain: float = 0.35
    effects_reduced: bool = False
    vibration_enabled: bool = False
    control_profile_id: str = "default"

    def __post_init__(self) -> None:
        for gain in (self.master_gain, self.effects_gain, self.music_gain):
            if not 0 <= gain <= 1:
                raise ValueError("audio gains must be between 0 and 1")
        if not self.control_profile_id:
            raise ValueError("control profile id must not be empty")


@dataclass(frozen=True, slots=True)
class RecordData:
    """Validated local score record identified by its ruleset version."""

    ruleset_version: str
    score: int
    best_fruit_level: int
    watermelons: int

    def __post_init__(self) -> None:
        if not self.ruleset_version:
            raise ValueError("ruleset version must not be empty")
        if min(self.score, self.best_fruit_level, self.watermelons) < 0:
            raise ValueError("record values must be non-negative")


class PersistencePort(Protocol):
    """Load and save validated JSON-backed settings and local records."""

    def load_settings(self) -> SettingsData | None: ...

    def save_settings(self, settings: SettingsData) -> None: ...

    def load_records(self) -> tuple[RecordData, ...]: ...

    def save_record(self, record: RecordData) -> None: ...


@dataclass(frozen=True, slots=True)
class SceneTransition:
    destination: str
    payload: tuple[tuple[str, str | int | float | bool | None], ...] = ()

    def __post_init__(self) -> None:
        if not self.destination:
            raise ValueError("scene destination must not be empty")
        if not isinstance(self.payload, tuple):
            raise TypeError("scene payload must be an immutable tuple")
        if any(not isinstance(item, tuple) or len(item) != 2 for item in self.payload):
            raise TypeError("scene payload entries must be key-value tuples")
        for key, value in self.payload:
            if not isinstance(key, str) or not key:
                raise ValueError("scene payload keys must be non-empty strings")
            if value is not None and type(value) not in (str, int, float, bool):
                raise TypeError("scene payload values must be immutable primitives")


class CanvasPort(Protocol):
    """Narrow draw target used by scenes without exposing a Pygame Surface."""

    def draw_session(
        self, snapshot: SessionSnapshot, events: tuple[DomainEvent, ...]
    ) -> None: ...


class Scene(Protocol):
    """Lifecycle and actions for one UI scene; transitions are explicit values."""

    def enter(self) -> None: ...

    def exit(self) -> None: ...

    def handle_actions(self, frame: InputFrame) -> SceneTransition | None: ...

    def update(self, delta_seconds: float) -> SceneTransition | None: ...

    def draw(self, canvas: CanvasPort) -> None: ...
