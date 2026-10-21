"""Integration checks for GameSession's fixed-step domain order."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from suika_elika.contracts import (
    BodySnapshot,
    ContactSnapshot,
    ControllerProfileData,
    EventType,
    FruitDefinition,
    InputAction,
    InputEdge,
    InputFrame,
    Pose,
    RecordData,
    RoundState,
    SettingsData,
    StatisticsData,
    Vector2,
)
from suika_elika.game.catalog import load_catalog
from suika_elika.game.danger import DangerState
from suika_elika.game.session import DEFAULT_FIXED_DT, GameSession

_ZERO_VECTOR = Vector2(0, 0)


@dataclass(frozen=True, slots=True)
class _Body:
    definition: FruitDefinition
    pose: Pose
    velocity: Vector2 = Vector2(0, 0)


class FakePhysics:
    def __init__(self) -> None:
        self.bodies: dict[str, _Body] = {}
        self.next_contacts: tuple[ContactSnapshot, ...] = ()
        self._contacts: tuple[ContactSnapshot, ...] = ()
        self.steps = 0

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 = _ZERO_VECTOR,
        angular_velocity: float = 0,
    ) -> None:
        del angular_velocity
        if entity_id in self.bodies:
            raise ValueError("duplicate body")
        self.bodies[entity_id] = _Body(definition, pose, velocity)

    def remove_body(self, entity_id: str) -> None:
        self.bodies.pop(entity_id, None)

    def step(self) -> None:
        self.steps += 1
        self._contacts = self.next_contacts
        self.next_contacts = ()

    def contacts(self) -> tuple[ContactSnapshot, ...]:
        return self._contacts

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        del center, radius
        return ()

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[BodySnapshot, ...]:
        return tuple(
            BodySnapshot(entity_id, body.pose, body.velocity)
            for entity_id in entity_ids
            if (body := self.bodies.get(entity_id)) is not None
        )


class FakePersistence:
    def __init__(self, records: tuple[RecordData, ...] = ()) -> None:
        self.records = records
        self.statistics = StatisticsData()
        self.saved_records: list[RecordData] = []
        self.saved_statistics: list[StatisticsData] = []

    def load_settings(self) -> SettingsData | None:
        return None

    def save_settings(self, settings: SettingsData) -> None:
        del settings

    def load_records(self) -> tuple[RecordData, ...]:
        return self.records

    def save_record(self, record: RecordData) -> None:
        self.saved_records.append(record)
        self.records = tuple(
            existing
            for existing in self.records
            if (existing.mode, existing.ruleset_version)
            != (record.mode, record.ruleset_version)
        ) + (record,)

    def load_profiles(self) -> tuple[()]:
        return ()

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None:
        del profiles

    def load_statistics(self) -> StatisticsData:
        return self.statistics

    def save_statistics(self, statistics: StatisticsData) -> None:
        self.saved_statistics.append(statistics)
        self.statistics = statistics


def _drop_frame(sequence: int) -> InputFrame:
    return InputFrame(edges=(InputEdge(sequence, InputAction.DROP),))


def _contact(first: str, second: str) -> ContactSnapshot:
    return ContactSnapshot(
        first_entity_id=first,
        second_entity_id=second,
        point=Vector2(400, 100),
        normal=Vector2(0, 1),
        impulse=1,
    )


def test_drop_snapshot_and_current_next_follow_the_accepted_fruit() -> None:
    physics = FakePhysics()
    session = GameSession(physics, seed=0)
    current = session.snapshot.current_fruit
    next_fruit = session.snapshot.next_fruit
    assert current is not None and next_fruit is not None

    events = session.step(_drop_frame(1))

    assert session.round_state is RoundState.PLAYING
    assert session.snapshot.current_fruit == next_fruit
    assert session.snapshot.next_fruit is not None
    assert session.snapshot.drop_ready is False
    assert len(session.snapshot.fruits) == 1
    dropped = session.snapshot.fruits[0]
    assert dropped.fruit_id == current.fruit_id
    assert dropped.current_pose.position == Vector2(400, -18)
    assert [event.event_type for event in events] == [EventType.FRUIT_DROPPED]
    assert session.drop_count == 1


def test_merge_precedes_danger_evaluation_and_scores_once() -> None:
    physics = FakePhysics()
    session = GameSession(physics, seed=0)
    session.step(_drop_frame(1))
    first_id = next(iter(physics.bodies))

    # Timeout safely releases the next drop when no fruit-pair contact arrives.
    for _ in range(120):
        session.step()
    assert session.snapshot.drop_ready
    session.step(_drop_frame(2))
    second_id = max(physics.bodies)
    assert physics.bodies[first_id].definition == physics.bodies[second_id].definition

    for entity_id in (first_id, second_id):
        previous = session._danger.state(entity_id)
        assert previous is not None
        session._danger._states[entity_id] = DangerState(
            entity_id=entity_id,
            danger_eligible=True,
            danger_seconds=1.5 - DEFAULT_FIXED_DT / 2,
            spawn_age_seconds=1.2,
            protected=False,
        )

    physics.next_contacts = (_contact(first_id, second_id),)
    events = session.step()

    assert len(physics.bodies) == 1
    child = next(iter(physics.bodies.values()))
    assert child.definition.fruit_id == "apple"
    assert session.score == child.definition.points_on_spawn
    assert session.merge_count == 1
    assert session.best_fruit_level == child.definition.level
    assert session.statistics.merges == 1
    assert session.statistics.best_fruit_level == child.definition.level
    child_id = next(iter(physics.bodies))
    child_danger = session._danger.state(child_id)
    assert child_danger is not None and child_danger.contact_age_seconds == 0
    assert sum(event.event_type is EventType.SCORE_CHANGED for event in events) == 1
    assert any(event.event_type is EventType.FRUIT_MERGED for event in events)
    assert session.round_state is RoundState.GAME_OVER
    assert next(
        index for index, event in enumerate(events)
        if event.event_type is EventType.FRUIT_MERGED
    ) < next(
        index for index, event in enumerate(events)
        if event.event_type is EventType.ROUND_ENDED
    )


def test_explicit_static_contact_unlocks_launcher_and_pause_freezes_state() -> None:
    physics = FakePhysics()
    session = GameSession(physics, seed=0)
    session.step(_drop_frame(1))
    launch_id = next(iter(physics.bodies))
    session.step(launch_contacted=True)
    danger_state = session._danger.state(launch_id)
    assert danger_state is not None and danger_state.contact_age_seconds == 0
    # Contact starts the 0.2 s minimum cooldown; elapsed time still applies.
    for _ in range(24):
        session.step()
    assert session.snapshot.drop_ready
    session.step(_drop_frame(2))
    assert session.drop_count == 2

    session.pause()
    paused_snapshot = session.snapshot
    steps = physics.steps
    session.step(_drop_frame(3), launch_contacted=True)
    assert physics.steps == steps
    assert session.snapshot == paused_snapshot

    session.resume()
    session.step()
    assert session.round_state is RoundState.PLAYING
    assert session.drop_count == 2
    assert launch_id in physics.bodies


def test_restart_removes_old_bodies_and_recreates_seeded_preview() -> None:
    physics = FakePhysics()
    session = GameSession(physics, seed=12)
    original_preview = session.snapshot.current_fruit
    session.step(_drop_frame(1))
    assert physics.bodies

    session.restart()

    assert physics.bodies == {}
    assert session.round_state is RoundState.READY
    assert session.score == 0 and session.drop_count == 0 and session.merge_count == 0
    assert session.snapshot.current_fruit == original_preview
    assert session.snapshot.fruits == ()


def test_record_is_scoped_by_mode_and_ruleset() -> None:
    catalog = load_catalog()
    persistence = FakePersistence(
        (
            RecordData(catalog.ruleset_version, 700, 4, 0, mode="other"),
            RecordData("old-rules", 900, 8, 1),
            RecordData(catalog.ruleset_version, 5, 2, 0),
        )
    )
    session = GameSession(FakePhysics(), catalog=catalog, persistence=persistence, seed=0)

    assert session.high_score == 5
    session.step(_drop_frame(1))
    first_id = next(iter(session._fruits))
    second_definition = session.snapshot.current_fruit
    assert second_definition is not None
    # Seed zero intentionally draws lemon twice, producing the 10-point apple.
    for _ in range(120):
        session.step()
    session.step(_drop_frame(2))
    second_id = max(session._fruits)
    physics = session._physics
    assert isinstance(physics, FakePhysics)
    physics.next_contacts = (_contact(first_id, second_id),)
    session.step()

    assert session.high_score == 10
    assert persistence.saved_records[-1].score == 10
    assert persistence.saved_records[-1].mode == "classic"
    assert persistence.saved_records[-1].ruleset_version == catalog.ruleset_version


def test_rejects_invalid_fixed_contact_and_movement_values() -> None:
    session = GameSession(FakePhysics())
    with pytest.raises(TypeError, match="launch_contacted"):
        session.step(launch_contacted=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="move_x"):
        session.step(InputFrame(move_x=2))
    assert DEFAULT_FIXED_DT > 0
