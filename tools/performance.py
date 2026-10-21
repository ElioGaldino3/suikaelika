"""Reproducible local frame, physics, cache, and allocation benchmark.

Run with ``python tools/performance.py``. The default uses SDL's dummy video
driver so the same timing path can be exercised without a physical display.
Measurements characterize this host only; they do not homologate Batocera.
"""

from __future__ import annotations

import argparse
import ctypes
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
    Pose,
    RoundState,
    SessionSnapshot,
    Vector2,
    make_event,
)
from suika_elika.game.catalog import load_catalog
from suika_elika.game.physics import PhysicsWorld
from suika_elika.rendering.renderer import Renderer


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
    *, frames: int, warmup: int, render_only: bool = False
) -> dict[str, object]:
    if frames <= 0 or warmup < 0:
        raise ValueError("frames must be positive and warmup must be non-negative")
    pygame.init()
    target = pygame.display.set_mode((1280, 720))
    renderer = Renderer(target)
    results: list[dict[str, float | int | str]] = []
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

        results.append(
            _timed_loop(scenario, draw_frame, frames=frames, warmup=warmup)
        )
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
    report = run_benchmark(
        frames=args.frames, warmup=args.warmup, render_only=args.render_only
    )
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized + "\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
