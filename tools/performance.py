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
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from suika_elika.contracts import (
    EventType,
    FruitSnapshot,
    InputAction,
    InputEdge,
    InputFrame,
    Pose,
    RoundState,
    SessionSnapshot,
    Vector2,
    make_event,
)
from suika_elika.game.battle import BattleSession
from suika_elika.game.catalog import load_catalog
from suika_elika.game.merging import MergeFruit, MergeSystem
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
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


def _record_comparison(seed: int) -> list[dict[str, Any]]:
    """Measure only record update logic on either side of the existing record."""
    results = []
    for label, current_score, old_score in (
        ("below_record", 900, 1000),
        ("above_record", 1100, 1000),
    ):
        persistence = _MemoryPersistence(old_score)
        from suika_elika.contracts import RecordData

        persistence.records = (
            RecordData(
                ruleset_version=load_catalog().ruleset_version,
                mode="classic",
                score=old_score,
                best_fruit_level=0,
                watermelons=0,
                duration_seconds=10.0,
            ),
        )
        session = GameSession(PhysicsWorld(), seed=seed, persistence=persistence)
        samples = []
        session._score = current_score
        for _ in range(120):
            started = time.perf_counter_ns()
            session._save_record()
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
        results.append(
            {
                "scenario": label,
                "seed": seed,
                "current_score": current_score,
                "previous_record": old_score,
                "save_calls": persistence.saves,
                "save_record_ms": _summarize(samples),
                "persistence": "in-memory stub; filesystem JSON I/O deliberately excluded",
            }
        )
    return results


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


def run_benchmark(*, frames: int, warmup: int, render_only: bool = False) -> dict[str, object]:
    if frames <= 0 or warmup < 0:
        raise ValueError("frames must be positive and warmup must be non-negative")
    pygame.init()
    target = pygame.display.set_mode((1280, 720))
    renderer = Renderer(target)
    results: list[dict[str, Any]] = []
    memory: dict[str, int] = {}

    for scenario, fruit_count, event_count, round_state in (
        ("normal_render_24_fruits", 24, 0, RoundState.PLAYING),
        ("reference_render_150_fruits", 150, 0, RoundState.PLAYING),
        ("stress_render_120_fruits_effects", 120, 3, RoundState.PLAYING),
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
        results.extend(_record_comparison(4417))

        # A bounded long session samples GC pauses and process/cache growth.
        long_session = GameSession(PhysicsWorld(), seed=4417, persistence=_MemoryPersistence())
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
        long_steps = max(1200, frames * 30)
        long_started = time.perf_counter_ns()
        for index in range(long_steps):
            edge = (InputEdge(index, InputAction.DROP),) if index % 42 == 0 else ()
            long_session.step(InputFrame(move_x=((index * 17 + 4417) % 121) / 60 - 1, edges=edge))
            _ = long_session.snapshot
        long_elapsed = (time.perf_counter_ns() - long_started) / 1_000_000
        gc.callbacks.remove(gc_probe)
        results.append(
            {
                "scenario": "classic_long_session",
                "seed": 4417,
                "action_sequence": "move_x=((tick*17+4417)%121)/60-1; DROP edge each 42 ticks",
                "fixed_steps": long_steps,
                "simulated_seconds": round(long_steps / 120, 2),
                "wall_elapsed_ms": round(long_elapsed, 3),
                "gc_pause_count": len(gc_pauses),
                "gc_pause_total_ms": round(sum(gc_pauses), 4),
                "gc_pause_p95_ms": round(_percentile(gc_pauses, 0.95), 4) if gc_pauses else 0.0,
                "gc_pause_max_ms": round(max(gc_pauses), 4) if gc_pauses else 0.0,
                "memory_end": dict(_process_memory()),
                "fruit_count_end": len(long_session.snapshot.fruits),
                "renderer_cache_bytes": 0,
                "note": (
                    "No renderer instantiated, so cache is not applicable. "
                    "Process memory is sampled only at the end."
                ),
            }
        )

    report = {
        "host": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "os": platform.platform(),
            "architecture": platform.machine(),
            "pygame": pygame.version.ver,
            "sdl": pygame.get_sdl_version(),
            "display_driver": pygame.display.get_driver(),
            "video_driver": os.environ.get("SDL_VIDEODRIVER", "system default"),
        },
        "configuration": {
            "logical_size": [1280, 720],
            "target_size": list(target.get_size()),
            "frames_per_scenario": frames,
            "warmup_frames": warmup,
            "render_only": render_only,
            "physics_fixed_dt": 1.0 / 120.0,
            "memory_note": (
                "tracemalloc covers Python allocations; Windows WorkingSet/PrivateUsage "
                "comes from PSAPI; SDL Surface bytes are separately estimated as "
                "pitch times height."
            ),
            "gc_note": (
                "GC pauses are sampled only in classic_long_session; other "
                "scenarios omit collection pauses."
            ),
            "scenario_note": (
                "Integrated domain steps are separate from isolated merge/render/physics "
                "workloads; none includes the full App loop or device I/O."
            ),
            "gc_enabled": gc.isenabled(),
        },
        "results": results,
        "surface_memory_bytes_estimate": memory,
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
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    report = run_benchmark(frames=args.frames, warmup=args.warmup, render_only=args.render_only)
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized + "\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
