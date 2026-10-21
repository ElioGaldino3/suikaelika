from __future__ import annotations

import random

from suika_elika.game.randomizer import FruitSequence


def test_same_seed_and_ruleset_reproduce_sequence() -> None:
    first = FruitSequence(8675309)
    second = FruitSequence(8675309)

    assert first.seed == 8675309
    assert first.ruleset_version == "classic-v2"
    for accepted in (True, False, True, True, False, True, True):
        assert first.try_consume_drop(accepted=accepted) == accepted
        assert second.try_consume_drop(accepted=accepted) == accepted
        assert (first.current, first.next) == (second.current, second.next)


def test_initial_sequence_draws_current_and_preview_from_only_launchable_fruits() -> None:
    sequence = FruitSequence("seed")

    assert 1 <= sequence.current.level <= 5
    assert 1 <= sequence.next.level <= 5
    assert sequence.accepted_drops == 0


def test_rejected_drop_does_not_advance_current_preview_or_random_state() -> None:
    sequence = FruitSequence(42)
    control = FruitSequence(42)
    before = (sequence.current, sequence.next)

    assert sequence.try_consume_drop(accepted=False) is False
    assert (sequence.current, sequence.next) == before
    assert sequence.accepted_drops == 0
    assert sequence.try_consume_drop(accepted=True) is True
    assert control.try_consume_drop(accepted=True) is True
    assert (sequence.current, sequence.next) == (control.current, control.next)


def test_fruit_sequence_randomness_is_independent_of_visual_generator() -> None:
    sequence = FruitSequence(123)
    control = FruitSequence(123)
    visual_rng = random.Random(987)

    observed: list[tuple[str, str]] = []
    expected: list[tuple[str, str]] = []
    for _ in range(20):
        visual_rng.random()
        observed.append((sequence.current.fruit_id, sequence.next.fruit_id))
        expected.append((control.current.fruit_id, control.next.fruit_id))
        sequence.try_consume_drop(accepted=True)
        control.try_consume_drop(accepted=True)

    assert observed == expected
