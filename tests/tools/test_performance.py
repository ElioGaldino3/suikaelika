"""Acceptance checks for deterministic, natural gameplay benchmark profiles."""

from __future__ import annotations

import pytest

from tools.performance import _accumulator_scenarios, _run_gameplay_replay


@pytest.mark.parametrize("mode", ("classic", "battle"))
def test_isolated_merge_profile_produces_one_natural_merge(mode: str) -> None:
    result = _run_gameplay_replay(mode, "isolated_merge")

    assert result["end_reason"] == "profile_limit"
    assert result["post_terminal_fixed_steps"] == 0
    assert result["boards"]
    for board in result["boards"]:
        assert board["drop_requested"] == 2
        assert board["drops_accepted"] == 2
        assert board["merge_events"] == 1
        assert board["cascade_links"] == []
        assert board["board_step_calls"] == result["fixed_steps"]


@pytest.mark.parametrize("mode", ("classic", "battle"))
def test_natural_cascade_records_child_parent_lineage(mode: str) -> None:
    result = _run_gameplay_replay(mode, "natural_cascade")

    assert result["end_reason"] == "cascade_settled"
    assert result["fixed_steps"] < 720
    for board in result["boards"]:
        assert board["merge_events"] >= 2
        assert board["cascade_links"]
        for link in board["cascade_links"]:
            assert link["followup_merge_tick"] > link["parent_merge_tick"]
            assert link["interval_ticks"] > 0
        assert board["board_step_calls"] == result["fixed_steps"]


@pytest.mark.parametrize(
    ("mode", "minimum_fruits"), (("classic", 40), ("battle", 40))
)
def test_dense_stack_profile_reaches_high_fruit_count(
    mode: str, minimum_fruits: int
) -> None:
    result = _run_gameplay_replay(mode, "dense_stack")

    assert result["fixed_steps"] > 6_000
    assert result["end_reason"] in {"profile_limit", "battle_finished"}
    assert all(
        board["max_fruit_count"] >= minimum_fruits for board in result["boards"]
    )


@pytest.mark.parametrize("mode", ("classic", "battle"))
def test_long_round_stops_on_natural_terminal_step(mode: str) -> None:
    result = _run_gameplay_replay(mode, "long_round")

    assert result["end_reason"] in {"game_over", "battle_finished"}
    assert result["post_terminal_fixed_steps"] == 0
    assert result["boards"]
    assert all(
        board["board_step_calls"] == result["fixed_steps"]
        for board in result["boards"]
    )
    if mode == "classic":
        assert result["boards"][0]["final_state"] == "game_over"
    else:
        assert result["battle_result"]["finished"] is True


def test_app_accumulator_probe_reports_bounded_catchup_and_discarded_backlog() -> None:
    scenarios = {item["scenario"]: item for item in _accumulator_scenarios()}

    steady = scenarios["steady_60_fps"]
    assert steady["fixed_steps_executed"] == 240
    assert steady["discarded_backlog_steps"] == 0

    stalled = scenarios["500ms_stall_capped_to_250ms"]
    assert stalled["clamped_frames"] == 1
    assert stalled["max_steps_per_frame"] == 8
    assert stalled["discarded_backlog_steps"] == 22
    assert stalled["accumulator_residual_ms"] < 1000 / 120
