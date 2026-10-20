"""Copied domain events that are safe to pass to presentation and audio."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import TypeAlias

from .models import Vector2


class EventType(str, Enum):
    FRUIT_DROPPED = "fruit_dropped"
    FRUIT_MERGED = "fruit_merged"
    SCORE_CHANGED = "score_changed"
    DANGER_CHANGED = "danger_changed"
    ROUND_ENDED = "round_ended"


EventValue: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """One event emitted by a simulation step, containing copied primitive data."""

    event_type: EventType
    step_index: int
    entity_ids: tuple[str, ...] = ()
    position: Vector2 | None = None
    payload: tuple[tuple[str, EventValue], ...] = ()

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("event step index must be non-negative")
        if not isinstance(self.entity_ids, tuple) or not isinstance(self.payload, tuple):
            raise TypeError("event ids and payload must be immutable tuples")
        if any(not isinstance(entity_id, str) or not entity_id for entity_id in self.entity_ids):
            raise ValueError("event entity identifiers must not be empty")
        if any(not isinstance(item, tuple) or len(item) != 2 for item in self.payload):
            raise TypeError("event payload entries must be key-value tuples")
        keys = [key for key, _ in self.payload]
        if any(not isinstance(key, str) or not key for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("event payload keys must be non-empty and unique")
        for _, value in self.payload:
            if value is not None and type(value) not in (str, int, float, bool):
                raise TypeError("event payload values must be immutable primitives")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError("event payload numbers must be finite")


def make_event(
    event_type: EventType,
    step_index: int,
    *,
    entity_ids: tuple[str, ...] = (),
    position: Vector2 | None = None,
    payload: tuple[tuple[str, EventValue], ...] = (),
) -> DomainEvent:
    """Build an event from copied values; physics callback objects do not cross."""

    return DomainEvent(event_type, step_index, entity_ids, position, payload)
