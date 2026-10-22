"""Immutable, engine-independent models shared between game components."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from math import isfinite


@dataclass(frozen=True, slots=True)
class Vector2:
    """A copied two-dimensional value in logical game coordinates."""

    x: float
    y: float

    def __post_init__(self) -> None:
        if not isfinite(self.x) or not isfinite(self.y):
            raise ValueError("vector coordinates must be finite")


@dataclass(frozen=True, slots=True)
class Pose:
    """A position and orientation copied from the simulation."""

    position: Vector2
    angle: float = 0.0

    def __post_init__(self) -> None:
        if not isfinite(self.angle):
            raise ValueError("pose angle must be finite")


@dataclass(frozen=True, slots=True)
class FruitDefinition:
    """Ruleset definition for one fruit kind; values contain no engine objects."""

    fruit_id: str
    level: int
    radius: float
    mass: float
    points_on_spawn: int
    visual_key: str

    def __post_init__(self) -> None:
        if not self.fruit_id or not self.visual_key:
            raise ValueError("fruit_id and visual_key must not be empty")
        if self.level < 1:
            raise ValueError("fruit level must be positive")
        if not isfinite(self.radius) or self.radius <= 0:
            raise ValueError("fruit radius must be finite and positive")
        if not isfinite(self.mass) or self.mass <= 0:
            raise ValueError("fruit mass must be finite and positive")
        if self.points_on_spawn < 0:
            raise ValueError("fruit points cannot be negative")


class RoundState(str, Enum):
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


UNKNOWN_PLAYER_ID = "unknown"
UNKNOWN_PLAYER_NAME = "Desconhecido"


def normalize_player_name(name: str) -> str:
    """Normalize a local player name according to the on-device naming rules."""
    if not isinstance(name, str):
        raise TypeError("player name must be text")
    normalized = " ".join(unicodedata.normalize("NFC", name).split())
    if not normalized or len(normalized) > 20:
        raise ValueError("player name must contain 1 to 20 code points")
    if normalized.casefold() == UNKNOWN_PLAYER_NAME.casefold():
        raise ValueError("Desconhecido is reserved")
    return normalized


@dataclass(frozen=True, slots=True)
class PlayerData:
    player_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.player_id or self.player_id == UNKNOWN_PLAYER_ID:
            raise ValueError("player id must be non-empty and not reserved")
        if normalize_player_name(self.name) != self.name:
            raise ValueError("player name must already be normalized")


@dataclass(frozen=True, slots=True)
class GameResultData:
    result_id: str
    player_id: str
    mode: str
    ruleset_version: str
    objective: str
    score: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if not all(
            (self.result_id, self.player_id, self.mode, self.ruleset_version, self.objective)
        ):
            raise ValueError("result identifiers and context must not be empty")
        if type(self.score) is not int or self.score < 0:
            raise ValueError("result score must be a non-negative integer")
        if (type(self.duration_seconds) not in (int, float) or
                not isfinite(self.duration_seconds) or self.duration_seconds < 0):
            raise ValueError("result duration must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class RecordCheckpointData:
    """An interrupted record candidate with elapsed active time at checkpoint."""
    result_id: str
    player_id: str
    mode: str
    ruleset_version: str
    objective: str
    score: int
    duration_seconds: float

    def __post_init__(self) -> None:
        GameResultData(self.result_id, self.player_id, self.mode, self.ruleset_version,
                       self.objective, self.score, self.duration_seconds)


@dataclass(frozen=True, slots=True)
class FruitSnapshot:
    """Render-safe fruit state copied from the simulation."""

    entity_id: str
    fruit_id: str
    previous_pose: Pose
    current_pose: Pose
    danger_eligible: bool
    danger_seconds: float

    def __post_init__(self) -> None:
        if not self.entity_id or not self.fruit_id:
            raise ValueError("fruit snapshot identifiers must not be empty")
        if not isfinite(self.danger_seconds) or self.danger_seconds < 0:
            raise ValueError("danger time must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Immutable public view of a game session for UI and presentation."""

    score: int
    high_score: int
    current_fruit: FruitDefinition | None
    next_fruit: FruitDefinition | None
    fruits: tuple[FruitSnapshot, ...]
    launcher_x: float
    drop_ready: bool
    danger_progress: float
    round_state: RoundState

    def __post_init__(self) -> None:
        if self.score < 0 or self.high_score < 0:
            raise ValueError("scores must be non-negative")
        if not isfinite(self.launcher_x):
            raise ValueError("launcher position must be finite")
        if not isfinite(self.danger_progress) or not 0 <= self.danger_progress <= 1:
            raise ValueError("danger progress must be between 0 and 1")
        if not isinstance(self.fruits, tuple):
            raise TypeError("fruits must be an immutable tuple")
