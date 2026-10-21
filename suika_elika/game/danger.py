"""Per-fruit protection, danger, recovery, and escape clocks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from math import isfinite

from suika_elika.contracts import Vector2


@dataclass(frozen=True, slots=True)
class DangerConfig:
    """Classic container and timer thresholds from PROJECT.md."""

    width: float = 800.0
    height: float = 460.0
    danger_y: float = 52.0
    protection_clearance: float = 8.0
    protection_contact_seconds: float = 0.8
    protection_launch_seconds: float = 1.2
    danger_entry_clearance: float = 4.0
    recovery_seconds: float = 0.12
    danger_limit_seconds: float = 1.5
    escape_limit_seconds: float = 0.6

    def __post_init__(self) -> None:
        positive = (
            self.width,
            self.height,
            self.protection_contact_seconds,
            self.protection_launch_seconds,
            self.recovery_seconds,
            self.danger_limit_seconds,
            self.escape_limit_seconds,
        )
        if any(not isfinite(value) or value <= 0 for value in positive):
            raise ValueError("world dimensions and danger durations must be positive")
        nonnegative = (self.protection_clearance, self.danger_entry_clearance, self.danger_y)
        if any(not isfinite(value) or value < 0 for value in nonnegative):
            raise ValueError("danger thresholds must be finite and non-negative")
        if self.danger_y >= self.height:
            raise ValueError("danger line must be inside the container")


@dataclass(frozen=True, slots=True)
class DangerObservation:
    """Copied body values for one simulation step; no physics objects cross here."""

    entity_id: str
    center: Vector2
    radius: float
    contacted: bool = False

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("danger observation entity_id must not be empty")
        if not isfinite(self.radius) or self.radius <= 0:
            raise ValueError("danger observation radius must be finite and positive")


@dataclass(frozen=True, slots=True)
class DangerState:
    """Simulation-time state owned by one active fruit entity."""

    entity_id: str
    danger_eligible: bool = False
    danger_seconds: float = 0.0
    spawn_age_seconds: float = 0.0
    contact_age_seconds: float | None = None
    recovery_age_seconds: float = 0.0
    escape_seconds: float = 0.0
    protected: bool = True

    @property
    def protection_age_seconds(self) -> float:
        """Oldest tracked age relevant to the finite initial protection window."""
        return max(self.spawn_age_seconds, self.contact_age_seconds or 0.0)


class GameOverReason(str, Enum):
    DANGER = "danger"
    ESCAPE = "escape"


@dataclass(frozen=True, slots=True)
class PhysicsDiagnostic:
    entity_id: str
    message: str


@dataclass(frozen=True, slots=True)
class DangerResult:
    """Current warning and terminal decision after resolving all live entities."""

    danger_progress: float
    warning_entity_id: str | None
    reason: GameOverReason | None
    game_over_entity_id: str | None
    diagnostics: tuple[PhysicsDiagnostic, ...] = ()


class DangerSystem:
    """Apply classic overflow rules per entity using simulation time only.

    ``update`` is called once after the physics/merge work for a fixed step. Callers
    should omit entities consumed by that step's merge before making the decision.
    """

    def __init__(self, config: DangerConfig | None = None) -> None:
        self.config = config or DangerConfig()
        self._states: dict[str, DangerState] = {}

    @property
    def states(self) -> tuple[DangerState, ...]:
        """Return immutable states ordered by entity ID."""
        return tuple(self._states[key] for key in sorted(self._states))

    def state(self, entity_id: str) -> DangerState | None:
        return self._states.get(entity_id)

    def register_spawn(self, entity_id: str) -> DangerState:
        """Start finite launch protection once; never reset an existing ID."""
        if not entity_id:
            raise ValueError("entity_id must not be empty")
        if entity_id in self._states:
            raise ValueError(f"danger state {entity_id!r} already exists")
        state = DangerState(entity_id=entity_id)
        self._states[entity_id] = state
        return state

    def register_merge(self, child_id: str, parent_ids: tuple[str, str]) -> DangerState:
        """Transfer risk and oldest protection ages to a replacement entity.

        A child becomes eligible as soon as either parent was eligible. If both
        parents remain protected, the greater elapsed age is preserved for each
        protection trigger, so a merge cannot refresh a launch/contact grace timer.
        """
        if not child_id or child_id in self._states:
            raise ValueError("child_id must be new and non-empty")
        if len(parent_ids) != 2 or parent_ids[0] == parent_ids[1]:
            raise ValueError("merge requires two different parent IDs")
        parents = tuple(self._states.get(parent_id) for parent_id in parent_ids)
        if any(parent is None for parent in parents):
            raise ValueError("both merge parents must have danger state")
        first, second = parents
        assert first is not None and second is not None
        protected = first.protected and second.protected
        contact_ages = tuple(
            age
            for age in (first.contact_age_seconds, second.contact_age_seconds)
            if age is not None
        )
        child = DangerState(
            entity_id=child_id,
            danger_eligible=(first.danger_eligible or second.danger_eligible or not protected),
            danger_seconds=max(first.danger_seconds, second.danger_seconds),
            spawn_age_seconds=max(first.spawn_age_seconds, second.spawn_age_seconds),
            contact_age_seconds=max(contact_ages) if contact_ages else None,
            recovery_age_seconds=max(first.recovery_age_seconds, second.recovery_age_seconds),
            escape_seconds=max(first.escape_seconds, second.escape_seconds),
            protected=protected,
        )
        self._states[child_id] = child
        return child

    def remove(self, entity_id: str) -> None:
        self._states.pop(entity_id, None)

    def update(
        self,
        observations: Iterable[DangerObservation],
        delta_seconds: float,
        *,
        paused: bool = False,
    ) -> DangerResult:
        """Advance clocks and decide danger/escape for the final live set."""
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("simulation delta must be finite and non-negative")
        if type(paused) is not bool:
            raise TypeError("paused must be a boolean")
        bodies = tuple(observations)
        by_id = {body.entity_id: body for body in bodies}
        if len(by_id) != len(bodies):
            raise ValueError("danger observations must have unique entity IDs")
        if paused:
            return self._result(by_id, ())

        diagnostics: list[PhysicsDiagnostic] = []
        next_states: dict[str, DangerState] = {}
        for entity_id in sorted(by_id):
            body = by_id[entity_id]
            state = self._states.get(entity_id) or DangerState(entity_id=entity_id)
            contact_age = state.contact_age_seconds
            if contact_age is None and body.contacted:
                contact_age = 0.0
            elif contact_age is not None:
                contact_age += delta_seconds

            spawn_age = state.spawn_age_seconds + delta_seconds
            top = body.center.y - body.radius
            protection_expired = (
                top >= self.config.danger_y + self.config.protection_clearance
                or (
                    contact_age is not None
                    and contact_age >= self.config.protection_contact_seconds
                )
                or spawn_age >= self.config.protection_launch_seconds
            )
            protected = state.protected and not protection_expired
            eligible = state.danger_eligible or not protected

            danger = state.danger_seconds
            recovery = state.recovery_age_seconds
            danger_line = self.config.danger_y - self.config.danger_entry_clearance
            clear_line = self.config.danger_y + self.config.protection_clearance
            if eligible:
                if top < danger_line:
                    danger += delta_seconds
                    recovery = 0.0
                elif top >= clear_line:
                    recovery += delta_seconds
                    if recovery >= self.config.recovery_seconds:
                        danger = 0.0
                        recovery = 0.0
                else:
                    recovery = 0.0

            outside_side_or_mouth = (
                body.center.x + body.radius < 0
                or body.center.x - body.radius > self.config.width
                or body.center.y + body.radius < 0
            )
            below_floor = body.center.y - body.radius > self.config.height
            escape = state.escape_seconds
            if below_floor:
                diagnostics.append(
                    PhysicsDiagnostic(
                        entity_id,
                        "body passed completely through the container floor",
                    )
                )
                escape = self.config.escape_limit_seconds
            elif not protected and outside_side_or_mouth:
                escape += delta_seconds
            else:
                escape = 0.0

            next_states[entity_id] = DangerState(
                entity_id=entity_id,
                danger_eligible=eligible,
                danger_seconds=danger,
                spawn_age_seconds=spawn_age,
                contact_age_seconds=contact_age,
                recovery_age_seconds=recovery,
                escape_seconds=escape,
                protected=protected,
            )

        self._states = next_states
        return self._result(by_id, tuple(diagnostics))

    def _result(
        self,
        bodies: dict[str, DangerObservation],
        diagnostics: tuple[PhysicsDiagnostic, ...],
    ) -> DangerResult:
        config = self.config
        ranked = sorted(
            (
                state
                for entity_id, state in self._states.items()
                if entity_id in bodies
            ),
            key=lambda state: (-state.danger_seconds, state.entity_id),
        )
        warning = ranked[0] if ranked else None
        highest = warning.danger_seconds if warning is not None else 0.0

        floor_failure = next(
            (item for item in diagnostics if "floor" in item.message), None
        )
        if floor_failure is not None:
            return DangerResult(
                danger_progress=min(1.0, highest / config.danger_limit_seconds),
                warning_entity_id=warning.entity_id if warning else None,
                reason=GameOverReason.ESCAPE,
                game_over_entity_id=floor_failure.entity_id,
                diagnostics=diagnostics,
            )

        fatal_escape = next(
            (
                state
                for state in sorted(self._states.values(), key=lambda value: value.entity_id)
                if state.entity_id in bodies and state.escape_seconds >= config.escape_limit_seconds
            ),
            None,
        )
        fatal_danger = next(
            (
                state
                for state in sorted(self._states.values(), key=lambda value: value.entity_id)
                if state.entity_id in bodies
                and state.danger_seconds >= config.danger_limit_seconds
            ),
            None,
        )
        reason: GameOverReason | None
        culprit: DangerState | None
        if fatal_escape is not None:
            reason, culprit = GameOverReason.ESCAPE, fatal_escape
        elif fatal_danger is not None:
            reason, culprit = GameOverReason.DANGER, fatal_danger
        else:
            reason = culprit = None
        return DangerResult(
            danger_progress=min(1.0, highest / config.danger_limit_seconds),
            warning_entity_id=warning.entity_id if warning else None,
            reason=reason,
            game_over_entity_id=culprit.entity_id if culprit else None,
            diagnostics=diagnostics,
        )


__all__ = [
    "DangerConfig",
    "DangerObservation",
    "DangerResult",
    "DangerState",
    "DangerSystem",
    "GameOverReason",
    "PhysicsDiagnostic",
]
