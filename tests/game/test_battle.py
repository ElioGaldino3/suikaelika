"""Battle rules exercised over real independent Pymunk sessions."""

import pytest

from suika_elika.contracts import InputAction, InputEdge, InputFrame, RoundState
from suika_elika.game.battle import BATTLE_WIDTH, BattleSession


def drop(sequence: int = 0, *, move_x: float = 0) -> InputFrame:
    return InputFrame(move_x=move_x, edges=(InputEdge(sequence, InputAction.DROP),))


def test_boards_have_independent_input_physics_and_identical_sequences() -> None:
    battle = BattleSession(seed=31)
    first, second = battle.players
    assert first.snapshot.current_fruit == second.snapshot.current_fruit
    assert first.snapshot.next_fruit == second.snapshot.next_fruit
    assert first.snapshot.launcher_x == BATTLE_WIDTH / 2
    battle.step((drop(move_x=-1), InputFrame(move_x=1)))
    assert first.drop_count == 1 and second.drop_count == 0
    assert first.snapshot.launcher_x < BATTLE_WIDTH / 2 < second.snapshot.launcher_x
    battle.step((InputFrame(), drop()))
    assert first.snapshot.fruits[0].fruit_id == second.snapshot.fruits[0].fruit_id
    assert first._physics is not second._physics


@pytest.mark.parametrize(
    ("scores", "winner"), [((1000, 0), 1), ((20, 1001), 2), ((1000, 1000), None)]
)
def test_target_is_at_least_1000_and_result_freezes_both_boards(scores, winner) -> None:
    battle = BattleSession()
    for player, score in zip(battle.players, scores, strict=True):
        player._score = score
    battle.step((InputFrame(), InputFrame()))
    assert battle.finished and battle.winner == winner and battle.reason == "target"
    before = battle.snapshot
    assert battle.step((drop(), drop())) == ()
    assert battle.snapshot == before


def test_999_does_not_finish_and_a_real_merge_reaches_1000() -> None:
    # Seed 2 starts with two apples. The merge contributes 15 points.
    battle = BattleSession(seed=2)
    player = battle.players[1]
    player._score = 999
    battle.step((InputFrame(), drop()))
    assert not battle.finished
    first_id = player.snapshot.fruits[0].entity_id
    body = player._physics._bodies[first_id]
    body.position = (180, 410)
    for _ in range(25):
        battle.step((InputFrame(), InputFrame()))
    battle.step((InputFrame(), drop(1)))
    fruit = player.snapshot.fruits[-1]
    player._physics._bodies[fruit.entity_id].position = (181, 410)
    for _ in range(5):
        battle.step((InputFrame(), InputFrame()))
        if battle.finished:
            break
    assert player.score > 999
    assert battle.finished and battle.winner == 2


@pytest.mark.parametrize("loser", [0, 1])
def test_real_overflow_awards_other_player(loser: int) -> None:
    battle = BattleSession()
    frames = [InputFrame(), InputFrame()]
    frames[loser] = drop()
    battle.step((frames[0], frames[1]))
    player = battle.players[loser]
    body = player._physics._bodies[player.snapshot.fruits[0].entity_id]
    for _ in range(400):
        body.position = (240, 20)
        body.velocity = (0, 0)
        battle.step((InputFrame(), InputFrame()))
        if battle.finished:
            break
    assert battle.finished and battle.winner == 2 - loser
    assert battle.reason == "overflow"


def test_simultaneous_overflow_draws_and_overflow_precedes_target() -> None:
    battle = BattleSession()
    battle.players[0]._round_state = RoundState.GAME_OVER
    battle.players[1]._score = 1000
    battle.step((InputFrame(), InputFrame()))
    assert battle.winner == 2 and battle.reason == "overflow"
    battle.restart()
    for player in battle.players:
        player._round_state = RoundState.GAME_OVER
    battle.step((InputFrame(), InputFrame()))
    assert battle.finished and battle.winner is None


def test_pause_freezes_both_and_restart_clears_result_and_fruits() -> None:
    battle = BattleSession()
    battle.step((drop(), drop()))
    battle.pause()
    before = battle.snapshot
    battle.step((InputFrame(), InputFrame()))
    assert battle.snapshot == before
    battle.resume()
    battle.step((InputFrame(), InputFrame()))
    assert battle.snapshot != before
    battle.restart()
    assert not battle.finished
    assert all(not player.snapshot.fruits and player.score == 0 for player in battle.players)


@pytest.mark.parametrize("target", [500, 0, -1, 3000, True, 1000.0])
def test_invalid_target_is_rejected_without_resetting_battle(target):
    battle = BattleSession()
    battle.players[0]._score = 50
    before = battle.snapshot
    with pytest.raises(ValueError):
        battle.restart(target=target)
    assert battle.snapshot == before
