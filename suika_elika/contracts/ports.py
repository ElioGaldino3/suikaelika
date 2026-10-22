"""Protocols at the boundaries between the domain and concrete adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from .events import DomainEvent
from .input import InputFrame
from .models import (
    FruitDefinition,
    GameResultData,
    PlayerData,
    Pose,
    RecordCheckpointData,
    SessionSnapshot,
    Vector2,
)

_ZERO_VELOCITY = Vector2(0.0, 0.0)


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

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 = _ZERO_VELOCITY,
        angular_velocity: float = 0.0,
    ) -> None: ...

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
    """Persistable audio, video, accessibility, layout, and collider preferences."""

    master_gain: float = 0.8
    effects_gain: float = 0.75
    music_gain: float = 0.35
    effects_reduced: bool = False
    vibration_enabled: bool = False
    control_profile_id: str = "default"
    fullscreen: bool = True
    safe_area_fraction: float = 0.05
    fruit_hitbox_scales: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        for gain in (self.master_gain, self.effects_gain, self.music_gain):
            if (
                type(gain) not in (int, float)
                or not math.isfinite(gain)
                or not 0 <= gain <= 1
            ):
                raise ValueError("audio gains must be between 0 and 1")
        if (
            not self.control_profile_id
            or type(self.effects_reduced) is not bool
            or type(self.vibration_enabled) is not bool
            or type(self.fullscreen) is not bool
        ):
            raise ValueError("settings flags and control profile id are invalid")
        if (
            type(self.safe_area_fraction) not in (int, float)
            or not math.isfinite(self.safe_area_fraction)
            or not 0 <= self.safe_area_fraction <= 0.25
        ):
            raise ValueError("safe area fraction must be between 0 and 0.25")
        if not isinstance(self.fruit_hitbox_scales, tuple):
            raise ValueError("fruit hitbox scales must be a tuple")
        seen_fruits: set[str] = set()
        for entry in self.fruit_hitbox_scales:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("each fruit hitbox scale must contain an id and scale")
            fruit_id, scale = entry
            if (
                not isinstance(fruit_id, str)
                or not fruit_id.strip()
                or fruit_id in seen_fruits
                or type(scale) not in (int, float)
                or not math.isfinite(scale)
                or not 0.5 <= scale <= 1.5
            ):
                raise ValueError("fruit hitbox scales must be unique values between 0.5 and 1.5")
            seen_fruits.add(fruit_id)


@dataclass(frozen=True, slots=True)
class RecordData:
    """Validated local record identified by game mode and ruleset version."""

    ruleset_version: str
    score: int
    best_fruit_level: int
    watermelons: int
    mode: str = "classic"
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.ruleset_version or not self.mode:
            raise ValueError("mode and ruleset version must not be empty")
        counters = (self.score, self.best_fruit_level, self.watermelons)
        if any(type(value) is not int or value < 0 for value in counters):
            raise ValueError("record values must be non-negative")
        if (
            type(self.duration_seconds) not in (int, float)
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds < 0
        ):
            raise ValueError("record duration must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ControllerProfileData:
    """Persistable semantic bindings and calibration for one stable device profile."""

    profile_id: str
    name: str
    backend: str
    bindings: tuple[tuple[str, str], ...]
    platform: str = "unknown"
    guid: str | None = None
    axes: tuple[tuple[str, int], ...] = ()
    inverted_axes: tuple[str, ...] = ()
    deadzone: float = 0.2
    sensitivity: float = 1.0

    def __post_init__(self) -> None:
        if not self.profile_id or not self.name or not self.backend or not self.platform:
            raise ValueError("profile id, name, backend, and platform must not be empty")
        if self.guid is not None and (not isinstance(self.guid, str) or not self.guid):
            raise ValueError("profile guid must be non-empty text or None")
        if not isinstance(self.bindings, tuple) or not isinstance(self.axes, tuple):
            raise TypeError("profile bindings and axes must be immutable tuples")
        if not isinstance(self.inverted_axes, tuple):
            raise TypeError("profile axis inversions must be an immutable tuple")
        if any(
            not isinstance(binding, tuple)
            or len(binding) != 2
            or not all(isinstance(value, str) and value for value in binding)
            for binding in self.bindings
        ):
            raise TypeError("profile bindings must contain non-empty string pairs")
        actions = [action for action, _ in self.bindings]
        if len(actions) != len(set(actions)):
            raise ValueError("profile actions must be unique")
        if any(
            not isinstance(axis, tuple)
            or len(axis) != 2
            or not isinstance(axis[0], str)
            or not axis[0]
            or type(axis[1]) is not int
            or axis[1] < 0
            for axis in self.axes
        ):
            raise TypeError("profile axes must contain non-empty names and non-negative indices")
        axis_names = [axis_name for axis_name, _ in self.axes]
        if len(axis_names) != len(set(axis_names)):
            raise ValueError("profile axis names must be unique")
        if any(not isinstance(name, str) or name not in axis_names for name in self.inverted_axes):
            raise ValueError("inverted axes must reference configured axes")
        if len(self.inverted_axes) != len(set(self.inverted_axes)):
            raise ValueError("inverted axes must be unique")
        if (
            type(self.deadzone) not in (int, float)
            or not math.isfinite(self.deadzone)
            or not 0 <= self.deadzone < 1
            or type(self.sensitivity) not in (int, float)
            or not math.isfinite(self.sensitivity)
            or self.sensitivity <= 0
        ):
            raise ValueError("profile deadzone and sensitivity are invalid")


@dataclass(frozen=True, slots=True)
class StatisticsData:
    """Accumulated local counters; no live or physical session state is stored."""

    sessions_played: int = 0
    merges: int = 0
    best_fruit_level: int = 0
    watermelons: int = 0

    def __post_init__(self) -> None:
        values = (
            self.sessions_played,
            self.merges,
            self.best_fruit_level,
            self.watermelons,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("statistics must be non-negative integers")


class PersistencePort(Protocol):
    """Load and save validated JSON-backed settings and local records."""

    def load_settings(self) -> SettingsData | None: ...

    def save_settings(self, settings: SettingsData) -> None: ...

    def load_records(self) -> tuple[RecordData, ...]: ...

    def save_record(self, record: RecordData) -> None: ...

    def load_profiles(self) -> tuple[ControllerProfileData, ...]: ...

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None: ...

    def load_statistics(self) -> StatisticsData: ...

    def save_statistics(self, statistics: StatisticsData) -> None: ...


class PlayerResultsPort(PersistencePort, Protocol):
    """Persistence capability for named players, results, and record checkpoints."""

    def load_players(self) -> tuple[PlayerData, ...]: ...

    def save_player(self, player: PlayerData) -> None: ...

    def load_results(self, mode: str | None = None) -> tuple[GameResultData, ...]: ...

    def save_result(self, result: GameResultData) -> None: ...

    def assign_result_player(self, result_id: str, player_id: str) -> GameResultData: ...

    def save_record_checkpoint(self, checkpoint: RecordCheckpointData) -> None: ...

    def finalize_record_checkpoint(self, result: GameResultData) -> None: ...


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
