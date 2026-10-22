"""Reproducible local frame, physics, cache, and allocation benchmark.

Run with ``python tools/performance.py``. The default uses SDL's dummy video
driver so the same timing path can be exercised without a physical display.
Measurements characterize this host only; they do not homologate Batocera.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import platform
import random
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from typing import Any

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from suika_elika.app import App
from suika_elika.audio import NullAudioManager, PygameAudioManager
from suika_elika.config import AppConfig
from suika_elika.contracts import (
    EventType,
    FruitSnapshot,
    InputAction,
    InputEdge,
    InputFrame,
    Pose,
    RecordData,
    RoundState,
    SessionSnapshot,
    Vector2,
    make_event,
)
from suika_elika.game.battle import BattleSession, BattleSnapshot
from suika_elika.game.catalog import load_catalog
from suika_elika.game.merging import MergeFruit, MergeSystem
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.persistence import JsonPersistence
from suika_elika.platform import UserPaths
from suika_elika.rendering.battle import BattleRenderer
from suika_elika.rendering.renderer import Renderer


class _MemoryPersistence:
    """Deterministic persistence stub; deliberately excludes filesystem latency."""

    def __init__(self, initial_score: int = 0) -> None:
        self.records: tuple[Any, ...] = ()
        self.saves = 0
        self.initial_score = initial_score

    def load_records(self) -> tuple[Any, ...]:
        return self.records

    def load_statistics(self) -> Any:
        from suika_elika.contracts import StatisticsData

        return StatisticsData()

    def save_record(self, record: Any) -> None:
        self.records = (record,)
        self.saves += 1

    def __getattr__(self, name: str) -> Any:
        if name.startswith("load_"):
            return lambda: None
        if name.startswith("save_"):
            return lambda *_args, **_kwargs: None
        raise AttributeError(name)


def _gameplay_benchmark(frames: int, seed: int, *, battle: bool) -> dict[str, Any]:
    """Run repeatable drop/move input through real session rules and physics."""
    persistence = _MemoryPersistence()
    session: Any = (
        BattleSession(seed=seed)
        if battle
        else GameSession(PhysicsWorld(), seed=seed, persistence=persistence)
    )
    step_samples: list[float] = []
    snapshot_samples: list[float] = []
    merge_steps: list[int] = []
    tracemalloc.start()
    allocation_start, _ = tracemalloc.get_traced_memory()
    for index in range(frames):
        # Seeded deterministic triangular movement; one edge every 42 fixed ticks.
        move = ((index * 17 + seed) % 121) / 60.0 - 1.0
        edges = (InputEdge(index, InputAction.DROP),) if index % 42 == 0 else ()
        frame = InputFrame(move_x=move, edges=edges)
        started = time.perf_counter_ns()
        if battle:
            events = session.step((frame, frame))
        else:
            events = session.step(frame)
        step_samples.append((time.perf_counter_ns() - started) / 1_000_000)
        if any(event.event_type is EventType.FRUIT_MERGED for event in events):
            merge_steps.append(index)
        started = time.perf_counter_ns()
        _ = session.snapshot
        snapshot_samples.append((time.perf_counter_ns() - started) / 1_000_000)
    alloc_current, alloc_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = frames / 120.0
    return {
        "scenario": "battle_integrated_steps" if battle else "classic_integrated_steps",
        "seed": seed,
        "action_sequence": "move_x=((tick*17+seed)%121)/60-1; DROP edge each 42 ticks",
        "fixed_steps": frames,
        "simulated_seconds": elapsed,
        "drops_requested": (frames + 41) // 42,
        "merge_step_indices": merge_steps,
        "merge_count": len(merge_steps),
        "step_ms": _summarize(step_samples),
        "snapshot_ms": _summarize(snapshot_samples),
        "python_alloc_delta_bytes": max(0, alloc_current - allocation_start),
        "python_alloc_peak_bytes": max(0, alloc_peak - allocation_start),
        "persistence": "none in battle; in-memory stub in classic",
        "note": ("Domain step plus snapshot; excludes App accumulator, SDL events, and devices."),
    }


_FIXED_DT = 1.0 / 120.0


def _replay_profile(mode: str, name: str) -> dict[str, Any]:
    if mode not in {"classic", "battle"}:
        raise ValueError("mode must be classic or battle")
    if name == "isolated_merge":
        if mode == "classic":
            return {
                "seed": 0,
                "max_ticks": 360,
                "drop_ticks": (0, 120),
                "drop_interval": None,
                "movement": "neutral",
                "action_sequence": "neutral x=400; DROP at ticks 0 and 120",
            }
        return {
            "seed": 2,
            "max_ticks": 180,
            "drop_ticks": (),
            "drop_interval": 90,
            "movement": "neutral",
            "action_sequence": "neutral x=240; DROP every 90 ticks from tick 0",
        }
    if name == "natural_cascade":
        if mode == "classic":
            return {
                "seed": 4417,
                "max_ticks": 720,
                "drop_ticks": (),
                "drop_interval": 42,
                "movement": "neutral",
                "action_sequence": "neutral x=400; DROP every 42 ticks from tick 0",
            }
        return {
            "seed": 2,
            "max_ticks": 720,
            "drop_ticks": (),
            "drop_interval": 90,
            "movement": "neutral",
            "action_sequence": "neutral x=240; DROP every 90 ticks from tick 0",
        }
    if name in {"dense_stack", "long_round"}:
        return {
            "seed": 4417,
            "max_ticks": 20_000 if name == "long_round" else 7_200,
            "drop_ticks": (),
            "drop_interval": 42,
            "movement": "seeded_sweep",
            "action_sequence": (
                "move_x=((tick*17+4417)%121)/60-1; DROP every 42 ticks from tick 0"
            ),
        }
    raise ValueError(f"unknown replay profile: {name}")


def _replay_frame(profile: dict[str, Any], tick: int) -> InputFrame:
    if profile["movement"] == "neutral":
        move_x = 0.0
    else:
        move_x = ((tick * 17 + profile["seed"]) % 121) / 60.0 - 1.0
    drop_ticks = profile["drop_ticks"]
    drop_interval = profile["drop_interval"]
    drop = tick in drop_ticks or (drop_interval is not None and tick % drop_interval == 0)
    edges = (InputEdge(tick, InputAction.DROP),) if drop else ()
    return InputFrame(move_x=move_x, edges=edges)


def _measure_method(
    owner: Any,
    name: str,
    samples: list[float],
    *,
    result_counts: list[int] | None = None,
) -> None:
    original = getattr(owner, name)

    def measured(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter_ns()
        result = original(*args, **kwargs)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
        if result_counts is not None:
            result_counts.append(len(result))
        return result

    setattr(owner, name, measured)


def _instrument_board(board: GameSession, metrics: dict[str, Any]) -> None:
    physics = board._physics
    _measure_method(physics, "step", metrics["physics_step_ms"])
    _measure_method(
        physics,
        "contacts",
        metrics["contacts_ms"],
        result_counts=metrics["contact_pair_counts"],
    )
    _measure_method(physics, "poses", metrics["poses_ms"])
    original_resolve = board._merger.resolve

    def measured_resolve(
        fruits: tuple[MergeFruit, ...],
        *,
        step_index: int,
        contacts: tuple[Any, ...] | None = None,
    ) -> Any:
        started = time.perf_counter_ns()
        resolution = original_resolve(
            fruits, step_index=step_index, contacts=contacts
        )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        metrics["merge_resolve_ms"].append(elapsed_ms)
        if elapsed_ms >= _FIXED_DT * 1000:
            metrics["slow_merge_samples"].append(
                {
                    "tick": step_index,
                    "duration_ms": round(elapsed_ms, 4),
                    "fruit_count": len(fruits),
                    "contact_count": len(contacts or ()),
                    "merged_pairs": len(resolution.merged_pairs),
                }
            )
        return resolution

    board._merger.resolve = measured_resolve
    if board._persistence is not None:
        _measure_method(board._persistence, "save_record", metrics["persistence_save_ms"])
        _measure_method(board, "_save_record", metrics["record_update_ms"])
    original_step = board.step

    def measured_step(
        frame: InputFrame | None = None, *, launch_contacted: bool = False
    ) -> tuple[Any, ...]:
        started = time.perf_counter_ns()
        events = original_step(frame, launch_contacted=launch_contacted)
        metrics["step_ms"].append((time.perf_counter_ns() - started) / 1_000_000)
        metrics["last_events"] = events
        return events

    board.step = measured_step


def _new_board_metrics() -> dict[str, Any]:
    return {
        "step_ms": [],
        "physics_step_ms": [],
        "contacts_ms": [],
        "poses_ms": [],
        "merge_resolve_ms": [],
        "slow_merge_samples": [],
        "record_update_ms": [],
        "persistence_save_ms": [],
        "contact_pair_counts": [],
        "last_events": (),
        "drop_requested": 0,
        "drops_accepted": 0,
        "merge_event_count": 0,
        "merge_ticks": [],
        "cascade_links": [],
        "children": {},
        "max_fruit_count": 0,
        "final_score": 0,
        "final_duration_seconds": 0.0,
        "final_state": "ready",
    }


def _record_replay_events(
    metrics: dict[str, Any], events: tuple[Any, ...], tick: int, round_number: int = 1
) -> None:
    for event in events:
        if event.event_type is EventType.FRUIT_DROPPED:
            metrics["drops_accepted"] += 1
        elif event.event_type is EventType.FRUIT_MERGED:
            metrics["merge_event_count"] += 1
            metrics["merge_ticks"].append(tick)
            entity_ids = event.entity_ids
            if len(entity_ids) < 3:
                continue
            parents, child_id = entity_ids[:-1], entity_ids[-1]
            for parent_id in parents:
                parent_merge_tick = metrics["children"].get(parent_id)
                if parent_merge_tick is not None:
                    metrics["cascade_links"].append(
                        {
                            "round": round_number,
                            "parent_merge_tick": parent_merge_tick,
                            "followup_merge_tick": tick,
                            "child_id": parent_id,
                            "interval_ticks": tick - parent_merge_tick,
                        }
                    )
            metrics["children"][child_id] = tick


def _public_board_metrics(metrics: dict[str, Any], board: GameSession) -> dict[str, Any]:
    result: dict[str, Any] = {
        "drop_requested": metrics["drop_requested"],
        "drops_accepted": metrics["drops_accepted"],
        "board_step_calls": len(metrics["step_ms"]),
        "merge_events": metrics["merge_event_count"],
        "merge_bearing_ticks": len(set(metrics["merge_ticks"])),
        "merge_ticks": metrics["merge_ticks"],
        "cascade_links": metrics["cascade_links"],
        "max_fruit_count": metrics["max_fruit_count"],
        "max_contact_pairs": max(metrics["contact_pair_counts"], default=0),
        "final_fruit_count": len(board.snapshot.fruits),
        "final_score": board.score,
        "active_seconds": round(board.duration_seconds, 4),
        "active_seconds_exact": metrics["final_duration_seconds"],
        "final_state": board.round_state.value,
        "record_update_ms": (
            _summarize(metrics["record_update_ms"])
            if metrics["record_update_ms"]
            else None
        ),
        "record_update_calls": len(metrics["record_update_ms"]),
        "persistence_save_ms": (
            _summarize(metrics["persistence_save_ms"])
            if metrics["persistence_save_ms"]
            else None
        ),
        "persistence_save_calls": len(metrics["persistence_save_ms"]),
        "slow_merge_samples_over_fixed_step_budget": metrics["slow_merge_samples"],
    }
    for key in (
        "step_ms",
        "physics_step_ms",
        "contacts_ms",
        "poses_ms",
        "merge_resolve_ms",
    ):
        result[key] = _summarize(metrics[key]) if metrics[key] else None
    return result


def _run_gameplay_replay(
    mode: str,
    name: str,
    *,
    target: Any | None = None,
    renderer: Any | None = None,
    audio_manager: Any | None = None,
    draw_every_ticks: int = 2,
    game: GameSession | None = None,
    audio_clock: list[float] | None = None,
) -> dict[str, Any]:
    """Replay recorded control actions through the real Pymunk game rules."""
    if draw_every_ticks <= 0:
        raise ValueError("draw_every_ticks must be positive")
    profile = _replay_profile(mode, name)
    is_battle = mode == "battle"
    game_or_battle: Any
    if game is not None:
        if is_battle:
            raise ValueError("a supplied GameSession can only run classic profiles")
        game_or_battle = game
        boards = (game,)
    elif is_battle:
        game_or_battle = BattleSession(seed=profile["seed"])
        boards = game_or_battle.players
    else:
        game_or_battle = GameSession(PhysicsWorld(), seed=profile["seed"])
        boards = (game_or_battle,)

    board_metrics = [_new_board_metrics() for _ in boards]
    for board, metrics in zip(boards, board_metrics, strict=True):
        _instrument_board(board, metrics)

    frame_samples: list[float] = []
    snapshot_samples: list[float] = []
    audio_samples: list[float] = []
    render_samples: list[float] = []
    total_step_samples: list[float] = []
    cascade_stop_tick: int | None = None
    end_reason = "profile_limit"
    executed_ticks = 0
    frame_started: int | None = None
    for tick in range(profile["max_ticks"]):
        if renderer is not None and tick % draw_every_ticks == 0:
            frame_started = time.perf_counter_ns()
        frames = tuple(_replay_frame(profile, tick) for _ in boards)
        for metrics, frame in zip(board_metrics, frames, strict=True):
            metrics["drop_requested"] += len(frame.edges)
        step_started = time.perf_counter_ns()
        if is_battle:
            returned_events = game_or_battle.step((frames[0], frames[1]))
            event_batches = tuple(metrics["last_events"] for metrics in board_metrics)
        else:
            returned_events = game_or_battle.step(frames[0])
            event_batches = (returned_events,)
        total_step_samples.append((time.perf_counter_ns() - step_started) / 1_000_000)
        executed_ticks += 1
        board_snapshots = []
        for metrics, board, events in zip(board_metrics, boards, event_batches, strict=True):
            _record_replay_events(metrics, events, tick)
            snapshot_started = time.perf_counter_ns()
            snapshot = board.snapshot
            snapshot_samples.append((time.perf_counter_ns() - snapshot_started) / 1_000_000)
            board_snapshots.append(snapshot)
            metrics["max_fruit_count"] = max(
                metrics["max_fruit_count"], len(snapshot.fruits)
            )
            metrics["final_score"] = board.score
            metrics["final_duration_seconds"] = board.duration_seconds
            metrics["final_state"] = board.round_state.value
            if metrics["cascade_links"] and cascade_stop_tick is None:
                if name == "natural_cascade":
                    cascade_stop_tick = tick + 60

        all_events = tuple(event for batch in event_batches for event in batch)
        if audio_manager is not None:
            if audio_clock is not None:
                audio_clock[0] = (tick + 1) * _FIXED_DT
            audio_started = time.perf_counter_ns()
            audio_manager.consume(all_events)
            audio_samples.append((time.perf_counter_ns() - audio_started) / 1_000_000)
        if renderer is not None:
            renderer.advance_presentation(_FIXED_DT, all_events)
            should_draw = (tick + 1) % draw_every_ticks == 0
            if should_draw:
                draw_started = time.perf_counter_ns()
                if is_battle:
                    battle_snapshot = BattleSnapshot(
                        tuple(board_snapshots),
                        game_or_battle.target,
                        game_or_battle.finished,
                        game_or_battle.winner,
                        game_or_battle.reason,
                    )
                    renderer.draw_battle(battle_snapshot)
                else:
                    renderer.draw_session(board_snapshots[0], ())
                pygame.display.flip()
                render_samples.append((time.perf_counter_ns() - draw_started) / 1_000_000)
                if frame_started is not None:
                    frame_samples.append((time.perf_counter_ns() - frame_started) / 1_000_000)
                    frame_started = None

        terminal = (
            game_or_battle.finished
            if is_battle
            else boards[0].round_state is RoundState.GAME_OVER
        )
        if terminal:
            end_reason = "battle_finished" if is_battle else "game_over"
            break
        if cascade_stop_tick is not None and tick >= cascade_stop_tick:
            end_reason = "cascade_settled"
            break

    target_surface = target if target is not None else getattr(renderer, "target", None)
    return {
        "scenario": name,
        "mode": mode,
        "seed": profile["seed"],
        "action_sequence": profile["action_sequence"],
        "fixed_steps": executed_ticks,
        "post_terminal_fixed_steps": 0,
        "end_reason": end_reason,
        "simulated_seconds": round(executed_ticks * _FIXED_DT, 4),
        "target_size": list(target_surface.get_size()) if target_surface is not None else None,
        "boards": [
            _public_board_metrics(metrics, board)
            for metrics, board in zip(board_metrics, boards, strict=True)
        ],
        "battle_result": (
            {
                "finished": game_or_battle.finished,
                "winner": game_or_battle.winner,
                "reason": game_or_battle.reason,
                "target": game_or_battle.target,
            }
            if is_battle
            else None
        ),
        "battle_step_ms": _summarize(total_step_samples) if is_battle else None,
        "snapshot_ms": _summarize(snapshot_samples),
        "render_batch_ms": _summarize(frame_samples) if frame_samples else None,
        "draw_every_fixed_ticks": draw_every_ticks if renderer is not None else None,
        "render_ms": _summarize(render_samples) if render_samples else None,
        "audio_consume_ms": _summarize(audio_samples) if audio_samples else None,
        "measurement_note": (
            "Natural seeded InputFrame replay with production GameSession/BattleSession, "
            "Pymunk physics, and event-derived merge lineage. Instrumented method timings "
            "include small wrapper overhead. Render timings cover batches of the configured "
            "fixed-step interval. App event polling and physical devices are excluded."
        ),
    }


def _summarize(samples: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(samples), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "p99_ms": round(_percentile(samples, 0.99), 4),
        "max_ms": round(max(samples), 4),
    }


def _merge_scenarios(seed: int) -> list[dict[str, Any]]:
    """Isolate real merge resolution over deterministic synthetic contacts."""
    catalog = load_catalog()
    results: list[dict[str, Any]] = []
    for name, pairs in (("merge_single", 1), ("merge_chain", 5), ("merge_dense", 16)):
        physics = PhysicsWorld()
        source = catalog.get("cherry").definition
        fruits = tuple(
            MergeFruit(
                f"merge-{index}",
                source,
                Pose(Vector2(100 + (index % 8) * 4, 120 + (index // 8) * 4)),
                Vector2(0, 0),
            )
            for index in range(pairs * 2)
        )
        for fruit in fruits:
            physics.create_body(fruit.entity_id, fruit.definition, fruit.pose)
        child_counter = iter(range(100_000))

        def next_child(
            counter: Any = child_counter, scenario: str = name, run_seed: int = seed
        ) -> str:
            return f"child-{run_seed}-{scenario}-{next(counter)}"

        merge = MergeSystem(catalog, physics, next_child)
        samples: list[float] = []
        merged = 0
        iterations = 5 if pairs >= 16 else 15
        for step in range(iterations):
            started = time.perf_counter_ns()
            resolution = merge.resolve(fruits, step_index=step)
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
            merged += len(resolution.merged_pairs)
        results.append(
            {
                "scenario": name,
                "seed": seed,
                "synthetic_fruit_count": len(fruits),
                "iterations": iterations,
                "merged_pairs_total": merged,
                "resolve_ms": _summarize(samples),
                "note": (
                    "Real MergeSystem.resolve over synthetic contacts; not a natural "
                    "physical cascade or gameplay replay."
                ),
            }
        )
    return results


def _accumulator_scenarios() -> list[dict[str, Any]]:
    """Probe the production App accumulator with steady, jittered, and stalled frames."""

    class _CountingManager:
        current_name = "play"

        def __init__(self) -> None:
            self.steps = 0

        def simulation_step(self) -> None:
            self.steps += 1

    steady = [1.0 / 60.0] * 120
    jittered = [value for _ in range(30) for value in (1.0 / 120.0, 1.0 / 30.0,
                                                          1.0 / 60.0, 1.0 / 30.0)]
    stalled = [1.0 / 60.0] * 60
    stalled[30] = 0.5
    results = []
    for name, elapsed_frames in (
        ("steady_60_fps", steady),
        ("jittered_frame_times", jittered),
        ("500ms_stall_capped_to_250ms", stalled),
    ):
        app = App(AppConfig(fullscreen=False))
        manager = _CountingManager()
        app._manager = manager
        samples: list[float] = []
        executed_steps = 0
        capped_seconds = 0.0
        clamped_frames = 0
        for elapsed in elapsed_frames:
            capped = min(elapsed, app.config.max_frame_delta)
            capped_seconds += capped
            clamped_frames += elapsed > app.config.max_frame_delta
            started = time.perf_counter_ns()
            executed_steps += app._advance_simulation(elapsed)
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
        unprocessed_seconds = max(
            0.0,
            capped_seconds - executed_steps * app.config.fixed_dt - app.accumulator,
        )
        results.append(
            {
                "scenario": name,
                "input_frames": len(elapsed_frames),
                "input_elapsed_seconds": round(sum(elapsed_frames), 4),
                "elapsed_after_frame_delta_cap_seconds": round(capped_seconds, 4),
                "clamped_frames": clamped_frames,
                "fixed_steps_executed": executed_steps,
                "manager_step_count": manager.steps,
                "discarded_backlog_steps": round(
                    unprocessed_seconds / app.config.fixed_dt
                ),
                "accumulator_residual_ms": round(app.accumulator * 1000, 4),
                "max_steps_per_frame": app.config.max_simulation_steps,
                "app_advance_ms": _summarize(samples),
            }
        )
    return results


def _record_data_as_dict(record: RecordData | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "mode": record.mode,
        "ruleset_version": record.ruleset_version,
        "score": record.score,
        "best_fruit_level": record.best_fruit_level,
        "watermelons": record.watermelons,
        "duration_seconds": record.duration_seconds,
    }


def _record_persistence_comparison(seed: int) -> list[dict[str, Any]]:
    """Replay complete rounds below/above a record with memory and durable JSON stores."""
    catalog = load_catalog()
    cases = (
        ("round_below_existing_record", 100_000),
        ("round_surpasses_existing_record", 0),
    )
    results: list[dict[str, Any]] = []
    scratch_root = Path(".local")
    scratch_root.mkdir(exist_ok=True)

    for case_name, old_score in cases:
        initial = RecordData(
            ruleset_version=catalog.ruleset_version,
            mode="classic",
            score=old_score,
            best_fruit_level=0,
            watermelons=0,
            duration_seconds=91.25,
        )
        for backend in ("memory_stub", "json_fsync_backup_replace"):
            temp_context: tempfile.TemporaryDirectory[str] | None = None
            json_store: JsonPersistence | None = None
            paths: UserPaths | None = None
            if backend == "memory_stub":
                persistence: Any = _MemoryPersistence()
                persistence.records = (initial,)
            else:
                temp_context = tempfile.TemporaryDirectory(
                    prefix="suika-performance-record-", dir=scratch_root
                )
                root = Path(temp_context.name)
                paths = UserPaths(root / "config", root / "data", root / "logs")
                json_store = JsonPersistence(paths)
                json_store.save_record(initial)
                json_store.last_error = None
                persistence = json_store

            game = GameSession(
                PhysicsWorld(), seed=seed, persistence=persistence
            )
            replay = _run_gameplay_replay("classic", "long_round", game=game)
            board = replay["boards"][0]
            final_score = int(board["final_score"])
            expected_relation = (
                final_score < old_score
                if case_name == "round_below_existing_record"
                else final_score > old_score
            )
            if not expected_relation:
                raise RuntimeError(
                    f"{case_name} did not exercise the requested score relation: "
                    f"round={final_score}, existing={old_score}"
                )

            reloaded: RecordData | None = None
            reload_error: str | None = None
            save_error = getattr(persistence, "last_error", None)
            if json_store is not None and paths is not None:
                fresh_store = JsonPersistence(paths)
                loaded_records = fresh_store.load_records()
                reloaded = next(
                    (
                        record
                        for record in loaded_records
                        if (record.mode, record.ruleset_version)
                        == ("classic", catalog.ruleset_version)
                    ),
                    None,
                )
                reload_error = fresh_store.last_error
                save_error = json_store.last_error
            else:
                reloaded = next(
                    (
                        record
                        for record in persistence.load_records()
                        if (record.mode, record.ruleset_version)
                        == ("classic", catalog.ruleset_version)
                    ),
                    None,
                )

            results.append(
                {
                    "scenario": case_name,
                    "backend": backend,
                    "seed": seed,
                    "action_sequence": replay["action_sequence"],
                    "fixed_steps": replay["fixed_steps"],
                    "active_seconds": board["active_seconds"],
                    "final_score": final_score,
                    "previous_score": old_score,
                    "previous_record_relation_verified": expected_relation,
                    "record_update_ms": board["record_update_ms"],
                    "record_update_calls": board["record_update_calls"],
                    "storage_save_ms": board["persistence_save_ms"],
                    "storage_save_calls": board["persistence_save_calls"],
                    "domain_step_ms": board["step_ms"],
                    "physics_step_ms": board["physics_step_ms"],
                    "contacts_ms": board["contacts_ms"],
                    "merge_resolve_ms": board["merge_resolve_ms"],
                    "record_after_round": _record_data_as_dict(reloaded),
                    "round_end_duration_matches_saved_record": (
                        abs(
                            reloaded.duration_seconds
                            - float(board["active_seconds_exact"])
                        ) <= _FIXED_DT / 2
                        if reloaded is not None and final_score > old_score
                        else None
                    ),
                    "saved_duration_delta_vs_game_over_seconds": (
                        round(
                            reloaded.duration_seconds
                            - float(board["active_seconds_exact"]),
                            6,
                        )
                        if reloaded is not None and final_score > old_score
                        else None
                    ),
                    "save_error": save_error,
                    "reload_error": reload_error,
                    "reload_verified": reloaded is not None and reload_error is None,
                    "note": (
                        "Memory stub and real JsonPersistence use identical natural "
                        "long-round input. JSON timing includes synchronous serialization, "
                        "flush/fsync, backup copy, and atomic replacement; initial record "
                        "setup is excluded."
                    ),
                }
            )
            if temp_context is not None:
                temp_context.cleanup()
    return results


def _audio_comparison(pygame_module: Any) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    simulated_time = [0.0]
    null_manager = NullAudioManager()
    null_replay = _run_gameplay_replay(
        "classic",
        "natural_cascade",
        audio_manager=null_manager,
        audio_clock=simulated_time,
    )
    results.append(
        {
            "backend": "null_audio_manager",
            "available": null_manager.available,
            "consume_ms": null_replay["audio_consume_ms"],
            "fixed_steps": null_replay["fixed_steps"],
            "merge_events": null_replay["boards"][0]["merge_events"],
            "last_error": null_manager.failure_reason,
        }
    )
    null_manager.close()

    real_manager: PygameAudioManager | None = None
    try:
        real_manager = PygameAudioManager(
            pygame_module, clock=lambda: simulated_time[0]
        )
        simulated_time[0] = 0.0
        real_replay = _run_gameplay_replay(
            "classic",
            "natural_cascade",
            audio_manager=real_manager,
            audio_clock=simulated_time,
        )
        results.append(
            {
                "backend": "pygame_mixer_dummy_driver",
                "available": real_manager.available,
                "consume_ms": real_replay["audio_consume_ms"],
                "fixed_steps": real_replay["fixed_steps"],
                "merge_events": real_replay["boards"][0]["merge_events"],
                "last_error": real_manager.last_error,
            }
        )
    except Exception as error:
        results.append(
            {
                "backend": "pygame_mixer_dummy_driver",
                "available": False,
                "consume_ms": None,
                "fixed_steps": None,
                "merge_events": None,
                "last_error": str(error) or type(error).__name__,
            }
        )
    finally:
        if real_manager is not None:
            real_manager.close()
    return {
        "scenarios": results,
        "driver": os.environ.get("SDL_AUDIODRIVER", "system default"),
        "simulated_audio_clock": True,
        "hardware_verified": False,
        "note": (
            "The Pygame mixer path is initialized and consumed through SDL's configured "
            "driver. A dummy driver does not measure HDMI, speaker, or Batocera latency."
        ),
    }


def _renderer_cache_snapshot(renderer: Renderer) -> dict[str, Any]:
    art = renderer.art
    extra_surfaces = tuple(
        surface
        for surface in (
            getattr(renderer, "_battle_background", None),
            getattr(renderer, "_battle_container", None),
            getattr(renderer, "_score_panel", None),
        )
        if surface is not None
    )
    art_cache_names = ("_fruit_cache", "_background_cache", "_container_cache")
    art_caches = {
        name.removeprefix("_"): len(value)
        for name in art_cache_names
        if isinstance((value := getattr(art, name, None)), dict)
    }
    return {
        "estimated_surface_bytes": _surface_bytes(renderer, renderer.target)
        + sum(
            surface.get_pitch() * surface.get_height()
            for surface in renderer._rotated_fruit_surfaces.values()
        )
        + sum(surface.get_pitch() * surface.get_height() for surface in extra_surfaces),
        "rotated_fruit_surfaces": len(renderer._rotated_fruit_surfaces),
        "rotated_fruit_surface_limit": 128,
        "small_fruit_surfaces": len(renderer._small_fruit_surfaces),
        "font_cache_entries": len(renderer._fonts),
        "effect_particles": len(renderer.effects.particles),
        "effect_particle_limit": renderer.effects.max_particles,
        "seen_effect_events": len(renderer.effects._seen_events),
        "seen_effect_event_limit": 512,
        "art_cache_entries": art_caches,
    }


def _long_session_soak(
    mode: str,
    renderer: Renderer,
    *,
    target_seconds: float,
    draw_every_ticks: int = 120,
) -> dict[str, Any]:
    """Keep one renderer alive across natural complete rounds for a multi-minute soak."""
    gc_pauses: list[float] = []
    gc_started: int | None = None

    def gc_probe(phase: str, _info: dict[str, Any]) -> None:
        nonlocal gc_started
        if phase == "start":
            gc_started = time.perf_counter_ns()
        elif phase == "stop" and gc_started is not None:
            gc_pauses.append((time.perf_counter_ns() - gc_started) / 1_000_000)
            gc_started = None

    gc.callbacks.append(gc_probe)
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    initial_allocated, _ = tracemalloc.get_traced_memory()
    memory_start = _process_memory()
    caches_start = _renderer_cache_snapshot(renderer)
    simulated_seconds = 0.0
    fixed_steps = 0
    round_results: list[dict[str, Any]] = []
    memory_samples: list[dict[str, Any]] = []
    soak_started = time.perf_counter_ns()
    try:
        while simulated_seconds < target_seconds:
            renderer.effects.clear()
            round_started = time.perf_counter_ns()
            result = _run_gameplay_replay(
                mode,
                "long_round",
                renderer=renderer,
                draw_every_ticks=draw_every_ticks,
            )
            if result["end_reason"] not in {"game_over", "battle_finished"}:
                raise RuntimeError(
                    f"{mode} long-round profile did not end naturally: "
                    f"{result['end_reason']} after {result['simulated_seconds']} seconds"
                )
            round_wall_ms = (time.perf_counter_ns() - round_started) / 1_000_000
            simulated_seconds += float(result["simulated_seconds"])
            fixed_steps += int(result["fixed_steps"])
            round_results.append(
                {
                    "number": len(round_results) + 1,
                    "active_seconds": result["simulated_seconds"],
                    "fixed_steps": result["fixed_steps"],
                    "end_reason": result["end_reason"],
                    "final_score": result["boards"][0]["final_score"],
                    "max_fruit_count": max(
                        board["max_fruit_count"] for board in result["boards"]
                    ),
                    "wall_elapsed_ms": round(round_wall_ms, 3),
                    "render_batch_ms": result["render_batch_ms"],
                    "board_stage_timings": [
                        {
                            key: board[key]
                            for key in (
                                "step_ms",
                                "physics_step_ms",
                                "contacts_ms",
                                "poses_ms",
                                "merge_resolve_ms",
                            )
                        }
                        for board in result["boards"]
                    ],
                }
            )
            allocated, peak_allocated = tracemalloc.get_traced_memory()
            memory_samples.append(
                {
                    "round": len(round_results),
                    "simulated_seconds": round(simulated_seconds, 3),
                    "python_allocated_bytes": allocated,
                    "python_peak_bytes": peak_allocated,
                    "process": _process_memory(),
                    "renderer_cache": _renderer_cache_snapshot(renderer),
                }
            )
    finally:
        gc.callbacks.remove(gc_probe)
        if not was_tracing:
            allocated, peak_allocated = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            allocated, peak_allocated = tracemalloc.get_traced_memory()
    wall_elapsed_ms = (time.perf_counter_ns() - soak_started) / 1_000_000
    memory_end = _process_memory()
    caches_end = _renderer_cache_snapshot(renderer)
    return {
        "mode": mode,
        "target_active_seconds": target_seconds,
        "actual_active_seconds": round(simulated_seconds, 4),
        "fixed_steps": fixed_steps,
        "round_count": len(round_results),
        "all_rounds_ended_naturally": all(
            result["end_reason"] in {"game_over", "battle_finished"}
            for result in round_results
        ),
        "wall_elapsed_ms": round(wall_elapsed_ms, 3),
        "simulated_to_wall_ratio": (
            round((simulated_seconds * 1000) / wall_elapsed_ms, 3)
            if wall_elapsed_ms
            else 0.0
        ),
        "gc_pause_count": len(gc_pauses),
        "gc_pause_total_ms": round(sum(gc_pauses), 4),
        "gc_pause_p95_ms": round(_percentile(gc_pauses, 0.95), 4) if gc_pauses else 0.0,
        "gc_pause_max_ms": round(max(gc_pauses), 4) if gc_pauses else 0.0,
        "python_allocated_delta_bytes": max(0, allocated - initial_allocated),
        "python_alloc_peak_bytes": max(0, peak_allocated - initial_allocated),
        "process_memory_start": memory_start,
        "process_memory_end": memory_end,
        "renderer_cache_start": caches_start,
        "renderer_cache_end": caches_end,
        "renderer_cache_samples": memory_samples,
        "rounds": round_results,
        "draw_every_fixed_ticks": draw_every_ticks,
        "note": (
            "Renderer persists across all naturally terminated rounds; the presentation "
            "effect queue is cleared at each match boundary. The requested duration counts "
            "active simulation only. Memory samples include the harness and Python allocator."
        ),
    }


def _full_scenario_suite(
    target: Any, *, seed: int, soak_seconds: float
) -> dict[str, Any]:
    renderers: dict[str, Renderer] = {}
    construction_ms: dict[str, float] = {}
    for mode, renderer_type in (
        ("classic", Renderer),
        ("battle", BattleRenderer),
    ):
        started = time.perf_counter_ns()
        renderers[mode] = renderer_type(target)
        construction_ms[mode] = round(
            (time.perf_counter_ns() - started) / 1_000_000, 4
        )

    replays: list[dict[str, Any]] = []
    replay_names = ("isolated_merge", "natural_cascade", "dense_stack", "long_round")
    no_audio = NullAudioManager()
    for mode, renderer in renderers.items():
        for name in replay_names:
            renderer.effects.clear()
            replay = _run_gameplay_replay(
                mode,
                name,
                renderer=renderer,
                audio_manager=no_audio,
                draw_every_ticks=4,
            )
            replay["renderer_cache_after"] = _renderer_cache_snapshot(renderer)
            replays.append(replay)

    accumulator = _accumulator_scenarios()
    persistence = _record_persistence_comparison(seed)
    audio = _audio_comparison(pygame)
    soak = [
        _long_session_soak(
            mode,
            renderer,
            target_seconds=soak_seconds,
        )
        for mode, renderer in renderers.items()
    ]
    no_audio.close()
    return {
        "configuration": {
            "seed": seed,
            "soak_target_seconds_per_mode": soak_seconds,
            "renderer_construction_ms": construction_ms,
            "scenario_names": replay_names,
            "render_every_fixed_ticks": 4,
            "long_soak_render_every_fixed_ticks": 120,
            "hardware_verified": False,
        },
        "replays": replays,
        "app_accumulator": accumulator,
        "record_persistence_comparison": persistence,
        "audio_comparison": audio,
        "long_session_soak": soak,
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def _process_memory() -> dict[str, int | str]:
    """Read process RSS/peak from Windows PSAPI or the portable resource API."""
    if os.name == "nt":
        from ctypes import wintypes

        class _ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        get_info = psapi.GetProcessMemoryInfo
        get_info.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            wintypes.DWORD,
        )
        get_info.restype = wintypes.BOOL
        if not get_info(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return {
            "source": "Windows PSAPI GetProcessMemoryInfo",
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
            "private_usage_bytes": int(counters.PrivateUsage),
        }

    try:
        import resource
    except ImportError:
        return {"source": "unavailable"}
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_bytes = value if sys.platform == "darwin" else value * 1024
    return {"source": "resource.getrusage peak RSS", "peak_rss_bytes": peak_bytes}


def _timed_loop(
    name: str,
    callback: Callable[[int], None],
    *,
    frames: int,
    warmup: int,
) -> dict[str, float | int | str]:
    for index in range(warmup):
        callback(index)
    memory_start = _process_memory()
    tracemalloc.start()
    before, _ = tracemalloc.get_traced_memory()
    samples: list[float] = []
    for index in range(frames):
        started = time.perf_counter_ns()
        callback(index + warmup)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_end = _process_memory()
    result: dict[str, float | int | str] = {
        "scenario": name,
        "samples": frames,
        "p50_ms": round(statistics.median(samples), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "p99_ms": round(_percentile(samples, 0.99), 4),
        "max_ms": round(max(samples), 4),
        "python_alloc_delta_bytes": max(0, current - before),
        "python_alloc_peak_bytes": max(0, peak - before),
    }
    for key in ("working_set_bytes", "private_usage_bytes"):
        if key in memory_start and key in memory_end:
            result[f"{key}_start"] = int(memory_start[key])
            result[f"{key}_end"] = int(memory_end[key])
    if "peak_working_set_bytes" in memory_end:
        result["process_peak_working_set_bytes"] = int(memory_end["peak_working_set_bytes"])
    elif "peak_rss_bytes" in memory_end:
        result["process_peak_rss_bytes"] = int(memory_end["peak_rss_bytes"])
    return result


def _snapshot(
    count: int, seed: int, *, round_state: RoundState = RoundState.PLAYING
) -> SessionSnapshot:
    catalog = load_catalog()
    entries = catalog.entries
    rng = random.Random(seed)
    fruits = tuple(
        FruitSnapshot(
            entity_id=f"bench-{index:04d}",
            fruit_id=entries[index % len(entries)].fruit_id,
            previous_pose=Pose(Vector2(rng.uniform(35, 765), rng.uniform(65, 440))),
            current_pose=Pose(Vector2(rng.uniform(35, 765), rng.uniform(65, 440))),
            danger_eligible=index % 7 == 0,
            danger_seconds=0.4 if index % 7 == 0 else 0.0,
        )
        for index in range(count)
    )
    return SessionSnapshot(
        score=1250,
        high_score=3000,
        current_fruit=entries[0].definition,
        next_fruit=entries[3].definition,
        fruits=fruits,
        launcher_x=400.0,
        drop_ready=True,
        danger_progress=0.25,
        round_state=round_state,
    )


def _merge_event(step: int, entity_base: int) -> Any:
    return make_event(
        EventType.FRUIT_MERGED,
        step,
        entity_ids=(f"left-{entity_base}", f"right-{entity_base}", f"merged-{entity_base}"),
        position=Vector2(400.0, 180.0),
    )


def _surface_bytes(renderer: Renderer, target: Any) -> int:
    surfaces = [
        target,
        renderer._logical,
        renderer._state_veil,
        renderer._background,
        renderer._container,
        *renderer._fruit_surfaces.values(),
        *renderer._small_fruit_surfaces.values(),
    ]
    if renderer._scaled_surface is not None:
        surfaces.append(renderer._scaled_surface)
    return sum(surface.get_pitch() * surface.get_height() for surface in surfaces)


def _physics_benchmark(count: int, *, frames: int, warmup: int) -> dict[str, float | int | str]:
    from suika_elika.contracts import Pose
    from suika_elika.game.catalog import load_catalog

    catalog = load_catalog()
    definition = catalog.get("cherry").definition
    world = PhysicsWorld()
    columns = max(1, int(count**0.5))
    for index in range(count):
        row, column = divmod(index, columns)
        world.create_body(
            f"bench-{index}",
            definition,
            Pose(Vector2(30.0 + column * 38.0, 28.0 + row * 20.0)),
        )
    return _timed_loop("physics", lambda _index: world.step(), frames=frames, warmup=warmup)


def run_benchmark(
    *,
    frames: int,
    warmup: int,
    render_only: bool = False,
    full_scenarios: bool = False,
    soak_seconds: float = 300.0,
) -> dict[str, object]:
    if frames <= 0 or warmup < 0:
        raise ValueError("frames must be positive and warmup must be non-negative")
    if full_scenarios and (
        render_only or not isfinite(soak_seconds) or soak_seconds <= 0
    ):
        raise ValueError("full scenarios need gameplay enabled and a positive soak duration")
    pygame.init()
    target = pygame.display.set_mode((1280, 720))
    renderer_started = time.perf_counter_ns()
    renderer = Renderer(target)
    renderer_construction_ms = (time.perf_counter_ns() - renderer_started) / 1_000_000
    results: list[dict[str, Any]] = []
    memory: dict[str, int] = {}

    for scenario, fruit_count, event_count, round_state in (
        ("normal_render_24_fruits", 24, 0, RoundState.PLAYING),
        ("reference_render_150_fruits", 150, 0, RoundState.PLAYING),
        ("render_120_fruits_no_effects", 120, 0, RoundState.PLAYING),
        ("render_120_fruits_with_effects", 120, 3, RoundState.PLAYING),
        ("paused_overlay", 24, 0, RoundState.PAUSED),
    ):
        renderer.effects.clear()
        snapshot = _snapshot(fruit_count, seed=2026, round_state=round_state)

        def draw_frame(
            index: int,
            *,
            frame_snapshot: SessionSnapshot = snapshot,
            merge_count: int = event_count,
        ) -> None:
            events = tuple(
                _merge_event(index, index * merge_count + event_index)
                for event_index in range(merge_count)
            )
            renderer.advance_presentation(1.0 / 60.0, events)
            renderer.draw_session(frame_snapshot, ())
            pygame.display.flip()

        results.append(_timed_loop(scenario, draw_frame, frames=frames, warmup=warmup))
        memory[scenario] = _surface_bytes(renderer, target)
        memory[f"{scenario}_particles_peak"] = len(renderer.effects.particles)

    if not render_only:
        for body_count, scenario in (
            (24, "normal_physics_24_bodies"),
            (120, "stress_physics_120_bodies"),
            (400, "diagnostic_physics_400_bodies"),
        ):
            result = _physics_benchmark(body_count, frames=frames, warmup=warmup)
            result["scenario"] = scenario
            results.append(result)

        # Integrated deterministic domain workloads for both game modes.
        results.append(_gameplay_benchmark(2400, 4417, battle=False))
        results.append(_gameplay_benchmark(2400, 4417, battle=True))
        results.extend(_merge_scenarios(4417))
    full_report = (
        _full_scenario_suite(target, seed=4417, soak_seconds=soak_seconds)
        if full_scenarios
        else None
    )
    effect_rows = {
        item["scenario"]: item
        for item in results
        if item["scenario"]
        in {"render_120_fruits_no_effects", "render_120_fruits_with_effects"}
    }
    no_effects = effect_rows.get("render_120_fruits_no_effects")
    with_effects = effect_rows.get("render_120_fruits_with_effects")
    effect_comparison = None
    if no_effects is not None and with_effects is not None:
        effect_comparison = {
            "fruit_count": 120,
            "round_state": RoundState.PLAYING.value,
            "no_effects": no_effects,
            "with_effects": with_effects,
            "p95_delta_ms": round(
                float(with_effects["p95_ms"]) - float(no_effects["p95_ms"]), 4
            ),
            "note": "Same seeded snapshot and draw path; only merge-effect event count changes.",
        }

    report = {
        "host": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "os": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor() or "unavailable",
            "logical_cpu_count": os.cpu_count(),
            "pygame": pygame.version.ver,
            "pymunk": version("pymunk"),
            "sdl": pygame.get_sdl_version(),
            "display_driver": pygame.display.get_driver(),
            "video_driver": os.environ.get("SDL_VIDEODRIVER", "system default"),
            "audio_driver": os.environ.get("SDL_AUDIODRIVER", "system default"),
        },
        "configuration": {
            "logical_size": [1280, 720],
            "target_size": list(target.get_size()),
            "frames_per_scenario": frames,
            "warmup_frames": warmup,
            "render_only": render_only,
            "full_scenarios": full_scenarios,
            "soak_seconds_per_mode": soak_seconds if full_scenarios else None,
            "renderer_construction_ms": round(renderer_construction_ms, 4),
            "physics_fixed_dt": 1.0 / 120.0,
            "memory_note": (
                "tracemalloc covers Python allocations; Windows WorkingSet/PrivateUsage "
                "comes from PSAPI; SDL Surface bytes are separately estimated as "
                "pitch times height."
            ),
            "gc_note": "Long-session soak reports GC pauses separately for each mode.",
            "scenario_note": (
                "Integrated domain steps are separate from isolated merge/render/physics "
                "workloads. Use --full-scenarios for natural replays, App accumulator, "
                "durable persistence, mixer, and multi-minute renderer soaks."
            ),
            "gc_enabled": gc.isenabled(),
        },
        "results": results,
        "controlled_render_effect_comparison": effect_comparison,
        "surface_memory_bytes_estimate": memory,
        "full_scenarios": full_report,
    }
    pygame.quit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Skip Pymunk body scenarios for a longer renderer run.",
    )
    parser.add_argument(
        "--full-scenarios",
        action="store_true",
        help="Run natural gameplay, persistence/audio comparisons, and long-session soaks.",
    )
    parser.add_argument(
        "--soak-seconds",
        type=float,
        default=300.0,
        help="Active simulation duration per mode for --full-scenarios (default: 300).",
    )
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    report = run_benchmark(
        frames=args.frames,
        warmup=args.warmup,
        render_only=args.render_only,
        full_scenarios=args.full_scenarios,
        soak_seconds=args.soak_seconds,
    )
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized + "\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
