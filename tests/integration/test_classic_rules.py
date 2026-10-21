"""Integration coverage for the classic session rules and recovery edges."""

from __future__ import annotations

from dataclasses import dataclass

from suika_elika.contracts import (
    BodySnapshot,
    ContactSnapshot,
    EventType,
    FruitDefinition,
    InputAction,
    InputEdge,
    InputFrame,
    Pose,
    RoundState,
    Vector2,
)
from suika_elika.game.catalog import load_catalog
from suika_elika.game.danger import DangerState
from suika_elika.game.session import DEFAULT_FIXED_DT, GameSession, _FruitState


@dataclass(frozen=True, slots=True)
class _Body:
    definition: FruitDefinition
    pose: Pose
    velocity: Vector2 = Vector2(0.0, 0.0)


class ScriptedPhysics:
    """PhysicsPort test double that exposes a fixed set of contacts per step."""

    def __init__(self) -> None:
        self.bodies: dict[str, _Body] = {}
        self.next_contacts: tuple[ContactSnapshot, ...] = ()
        self._contacts: tuple[ContactSnapshot, ...] = ()
        self.blocked_spawn = False
        self.step_count = 0

    def create_body(
        self,
        entity_id: str,
        definition: FruitDefinition,
        pose: Pose,
        *,
        velocity: Vector2 | None = None,
        angular_velocity: float = 0.0,
    ) -> None:
        del angular_velocity
        if entity_id in self.bodies:
            raise ValueError("duplicate entity id")
        self.bodies[entity_id] = _Body(definition, pose, velocity or Vector2(0.0, 0.0))

    def remove_body(self, entity_id: str) -> None:
        self.bodies.pop(entity_id, None)

    def step(self) -> None:
        self.step_count += 1
        self._contacts = self.next_contacts
        self.next_contacts = ()

    def contacts(self) -> tuple[ContactSnapshot, ...]:
        return self._contacts

    def overlaps(self, center: Vector2, radius: float) -> tuple[str, ...]:
        del center, radius
        return ("pile-blocker",) if self.blocked_spawn else ()

    def poses(self, entity_ids: tuple[str, ...]) -> tuple[BodySnapshot, ...]:
        return tuple(
            BodySnapshot(entity_id, body.pose, body.velocity)
            for entity_id in entity_ids
            if (body := self.bodies.get(entity_id)) is not None
        )


def _contact(first: str, second: str) -> ContactSnapshot:
    return ContactSnapshot(
        first_entity_id=first,
        second_entity_id=second,
        point=Vector2(200.0, 100.0),
        normal=Vector2(0.0, 1.0),
        impulse=1.0,
    )


def _place_fruit(
    session: GameSession,
    physics: ScriptedPhysics,
    entity_id: str,
    fruit_id: str,
    x: float,
    y: float,
) -> None:
    definition = load_catalog().get(fruit_id).definition
    pose = Pose(Vector2(x, y))
    physics.create_body(entity_id, definition, pose)
    session._fruits[entity_id] = _FruitState(definition, pose, pose, Vector2(0.0, 0.0))
    session._danger.register_spawn(entity_id)


def test_concurrent_merges_resolve_before_same_step_overflow_decision() -> None:
    physics = ScriptedPhysics()
    session = GameSession(physics, seed=9)
    for first, second, x in (("a", "b", 100.0), ("c", "d", 250.0)):
        _place_fruit(session, physics, first, "cherry", x, 160.0)
        _place_fruit(session, physics, second, "cherry", x + 24.0, 160.0)
    _place_fruit(session, physics, "overflow", "lemon", 500.0, 50.0)
    session._danger._states["overflow"] = DangerState(
        entity_id="overflow",
        danger_eligible=True,
        danger_seconds=1.5 - DEFAULT_FIXED_DT,
        spawn_age_seconds=2.0,
        protected=False,
    )
    physics.next_contacts = (_contact("d", "c"), _contact("b", "a"))

    events = session.step()

    merge_events = [event for event in events if event.event_type is EventType.FRUIT_MERGED]
    end_events = [event for event in events if event.event_type is EventType.ROUND_ENDED]
    score_events = [event for event in events if event.event_type is EventType.SCORE_CHANGED]
    assert len(merge_events) == 2
    assert len(end_events) == 1
    assert len(score_events) == 1
    assert dict(score_events[0].payload)["delta"] == 2
    assert session.score == 2
    assert session.merge_count == 2
    assert session.round_state is RoundState.GAME_OVER
    assert session._fruits.keys() == {"fruit-000001", "fruit-000002", "overflow"}
    assert max(events.index(event) for event in merge_events) < events.index(end_events[0])


def test_blocked_spawn_preserves_preview_and_does_not_queue_the_rejected_edge() -> None:
    physics = ScriptedPhysics()
    session = GameSession(physics, seed=21)
    initial_current = session.snapshot.current_fruit
    initial_next = session.snapshot.next_fruit
    physics.blocked_spawn = True

    rejected_events = session.step(
        InputFrame(edges=(InputEdge(1, InputAction.DROP),))
    )

    assert not any(event.event_type is EventType.FRUIT_DROPPED for event in rejected_events)
    assert session.drop_count == 0
    assert session.snapshot.current_fruit == initial_current
    assert session.snapshot.next_fruit == initial_next
    assert physics.bodies == {}

    physics.blocked_spawn = False
    session.step()  # Let the launcher observe that the spawn area is clear.
    assert session.snapshot.drop_ready
    accepted_events = session.step(
        InputFrame(edges=(InputEdge(2, InputAction.DROP),))
    )

    assert sum(event.event_type is EventType.FRUIT_DROPPED for event in accepted_events) == 1
    assert session.drop_count == 1
    assert session.snapshot.current_fruit == initial_next


def test_pause_discards_edges_and_repeated_restarts_replay_the_seeded_preview() -> None:
    physics = ScriptedPhysics()
    session = GameSession(physics, seed=73)
    preview = (session.snapshot.current_fruit, session.snapshot.next_fruit)
    session.step(InputFrame(edges=(InputEdge(1, InputAction.DROP),)))
    assert session.drop_count == 1

    session.pause()
    stopped_steps = physics.step_count
    session.step(InputFrame(edges=(InputEdge(2, InputAction.DROP),)))
    assert physics.step_count == stopped_steps
    assert session.drop_count == 1
    session.resume()
    session.step()
    assert session.drop_count == 1

    for sequence in range(3, 6):
        session.restart()
        assert session.round_state is RoundState.READY
        assert session.score == session.drop_count == session.merge_count == 0
        assert session.snapshot.fruits == ()
        assert (session.snapshot.current_fruit, session.snapshot.next_fruit) == preview
        session.step(InputFrame(edges=(InputEdge(sequence, InputAction.DROP),)))
        assert session.drop_count == 1
