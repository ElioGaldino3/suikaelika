"""Collect portable Python and package metadata without touching SDL or devices."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import struct
import sys
from collections.abc import Sequence
from typing import Any

LIBRARIES: dict[str, dict[str, str]] = {
    "runtime": {"pygame": "pygame", "pymunk": "pymunk"},
    "development": {"pytest": "pytest", "ruff": "ruff", "mypy": "mypy"},
}


def inspect_library(module_name: str, distribution_name: str) -> dict[str, Any]:
    """Inspect package presence without importing the package itself."""
    module_available: bool | None
    module_error: str | None = None
    try:
        module_available = importlib.util.find_spec(module_name) is not None
    except Exception as error:  # Keep a partial report if the import path is unusual.
        module_available = None
        module_error = type(error).__name__

    version: str | None = None
    metadata_error: str | None = None
    try:
        version = importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception as error:  # Metadata can fail independently of module discovery.
        metadata_error = type(error).__name__

    if module_available is True and version is not None:
        status = "available"
    elif module_available is True:
        status = "module_found_version_unknown"
    elif module_available is False and version is not None:
        status = "metadata_found_module_missing"
    elif module_available is False and metadata_error is None:
        status = "missing"
    else:
        status = "inspection_partial"

    result: dict[str, Any] = {
        "status": status,
        "module_available": module_available,
        "distribution_version": version,
    }
    if module_error is not None:
        result["module_error_type"] = module_error
    if metadata_error is not None:
        result["metadata_error_type"] = metadata_error
    return result


def collect_report() -> dict[str, Any]:
    """Return machine-readable environment facts and explicit untested capabilities."""
    libraries = {
        group: {
            name: inspect_library(name, distribution) for name, distribution in packages.items()
        }
        for group, packages in LIBRARIES.items()
    }
    return {
        "report_version": 1,
        "runtime": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "os_name": sys.platform,
            "system": platform.system(),
            "system_release": platform.release(),
            "machine": platform.machine() or "unknown",
            "process_architecture_bits": struct.calcsize("P") * 8,
        },
        "libraries": libraries,
        "device_probes": {
            "pygame_sdl": "not_run",
            "display": "not_run",
            "audio": "not_run",
            "joystick": "not_run",
            "note": (
                "This report reads Python package metadata only. It does not import Pygame, "
                "initialize SDL, open a display, or access audio or controllers."
            ),
        },
    }


def format_text(report: dict[str, Any]) -> str:
    """Render a concise report suitable for a terminal or a support ticket."""
    runtime = report["runtime"]
    lines = [
        "Suika Elika environment report",
        f"Python: {runtime['python_version']} ({runtime['python_implementation']})",
        f"OS: {runtime['system']} {runtime['system_release']} ({runtime['os_name']})",
        f"Architecture: {runtime['machine']}, {runtime['process_architecture_bits']}-bit process",
        "Libraries:",
    ]
    for group, packages in report["libraries"].items():
        lines.append(f"  {group}:")
        for name, info in packages.items():
            version = info["distribution_version"] or "version unknown"
            lines.append(f"    {name}: {info['status']} ({version})")
    lines.extend(
        [
            "Device probes: not run (no SDL, display, audio, or controller access)",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    args = parser.parse_args(argv)

    report = collect_report()
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
