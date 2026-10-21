"""Simulation-time checks for per-fruit overflow and escape rules."""

from __future__ import annotations

import pytest

from suika_elika.contracts import Vector2
from suika_elika.game.danger import (
    DangerObservation,
    DangerSystem,
    GameOverReason,
)


def _body(
    entity_id: str,
    *,
    x: float = 400.0,
    y: float = 100.0,
    radius: float = 14.0,
    contacted: bool = False,
) -> DangerObservation:
    return DangerObservation(entity_id, Vector2(x, y), radius, contacted)


def test_new_fruit_is_protected_until_first_clearance_contact_or_timeout() -> None:
    system = DangerSystem()
    system.register_spawn("new")

    initial = system.update((_body("new", y=50),), 0.7)
    state = system.state("new")
    assert state is not None and state.protected
    assert not state.danger_eligible
    assert initial.danger_progress == 0.0

    after_contact = system.update((_body("new", y=50, contacted=True),), 0.0)
    assert system.state("new").protected  # type: ignore[union-attr]
    contacted_window = system.update((_body("new", y=50),), 0.8)
    assert not system.state("new").protected  # type: ignore[union-attr]
    assert system.state("new").danger_eligible  # type: ignore[union-attr]
    assert contacted_window.danger_progress > 0.5
    assert after_contact.reason is None


def test_mouth_pile_warns_by_worst_individual_fruit_not_sum() -> None:
    system = DangerSystem()
    for entity_id in ("a-risk", "b-risk", "clear"):
        system.register_spawn(entity_id)
    system.update(
        (_body("a-risk", y=74), _body("b-risk", y=74), _body("clear", y=74)),
        0.0,
    )

    result = system.update(
        (_body("a-risk", y=61), _body("b-risk", y=61), _body("clear", y=74)),
        0.7,
    )

    assert system.state("a-risk").danger_seconds == pytest.approx(0.7)  # type: ignore[union-attr]
    assert system.state("b-risk").danger_seconds == pytest.approx(0.7)  # type: ignore[union-attr]
    assert result.warning_entity_id == "a-risk"  # stable tie-break by ID
    assert result.danger_progress == pytest.approx(0.7 / 1.5)
    assert result.reason is None  # 1.4 s summed risk is not a loss


def test_hysteresis_holds_danger_then_requires_consecutive_recovery() -> None:
    system = DangerSystem()
    system.register_spawn("stack")
    system.update((_body("stack", y=74),), 0.0)  # top=60 releases protection
    system.update((_body("stack", y=61),), 0.5)  # top=47 starts danger timer
    assert system.state("stack").danger_seconds == pytest.approx(0.5)  # type: ignore[union-attr]

    system.update((_body("stack", y=68),), 0.4)  # top=54: hold without counting
    assert system.state("stack").danger_seconds == pytest.approx(0.5)  # type: ignore[union-attr]
    system.update((_body("stack", y=74),), 0.06)  # top=60: begin recovery
    assert system.state("stack").danger_seconds == pytest.approx(0.5)  # type: ignore[union-attr]
    system.update((_body("stack", y=68),), 0.08)  # hold band breaks recovery
    assert system.state("stack").danger_seconds == pytest.approx(0.5)  # type: ignore[union-attr]
    system.update((_body("stack", y=74),), 0.12)
    assert system.state("stack").danger_seconds == 0.0  # type: ignore[union-attr]


def test_merge_inherits_danger_and_does_not_refresh_protection_age() -> None:
    system = DangerSystem()
    system.register_spawn("older")
    system.register_spawn("younger")
    system.update(
        (_body("older", y=50, contacted=True), _body("younger", y=50, contacted=True)),
        0.4,
    )
    child = system.register_merge("child", ("older", "younger"))
    assert child.protected
    assert child.protection_age_seconds == pytest.approx(0.4)

    # Child's prior protection ages continue; they do not restart at zero.
    system.update((_body("child", y=50),), 0.4)
    assert system.state("child").protected  # type: ignore[union-attr]
    result = system.update((_body("child", y=50),), 0.4)
    child_state = system.state("child")
    assert child_state is not None
    assert not child_state.protected
    assert child_state.danger_eligible
    assert child_state.danger_seconds == pytest.approx(0.4)
    assert result.reason is None


def test_pause_freezes_per_fruit_timers_and_consumed_entity_cannot_end_round() -> None:
    system = DangerSystem()
    system.register_spawn("fruit")
    system.update((_body("fruit", y=74),), 0.0)
    system.update((_body("fruit", y=61),), 1.2)
    assert system.state("fruit").danger_seconds == pytest.approx(1.2)  # type: ignore[union-attr]

    paused = system.update((_body("fruit", y=61),), 50.0, paused=True)
    assert paused.reason is None
    assert system.state("fruit").danger_seconds == pytest.approx(1.2)  # type: ignore[union-attr]

    # A merge can remove the parent before the terminal decision for this step.
    removed = system.update((), 0.5)
    assert removed.reason is None
    assert system.state("fruit") is None


def test_escape_timer_starts_after_protection_resets_inside_and_causes_escape() -> None:
    system = DangerSystem()
    system.register_spawn("outside")
    outside = _body("outside", x=-30, y=100)
    system.update((outside,), 0.0)  # top=86 ends initial protection
    not_yet = system.update((outside,), 0.3)
    assert not_yet.reason is None
    assert system.state("outside").escape_seconds == pytest.approx(0.3)  # type: ignore[union-attr]

    system.update((_body("outside", x=100),), 0.1)
    assert system.state("outside").escape_seconds == 0.0  # type: ignore[union-attr]
    result = system.update((outside,), 0.6)
    assert result.reason is GameOverReason.ESCAPE
    assert result.game_over_entity_id == "outside"


def test_floor_tunneling_is_reported_as_controlled_escape() -> None:
    system = DangerSystem()
    system.register_spawn("escaped")
    result = system.update((_body("escaped", y=480),), 1.2)

    assert result.reason is GameOverReason.ESCAPE
    assert result.game_over_entity_id == "escaped"
    assert result.diagnostics
    assert "floor" in result.diagnostics[0].message


@pytest.mark.parametrize("delta", [-0.1, float("nan")])
def test_update_rejects_invalid_simulation_delta(delta: float) -> None:
    with pytest.raises(ValueError, match="simulation delta"):
        DangerSystem().update((), delta)
