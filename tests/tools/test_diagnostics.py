"""Tests for the portable, non-invasive environment report."""

from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import diagnostics


def test_report_contains_runtime_and_separates_device_probes() -> None:
    report = diagnostics.collect_report()

    assert report["report_version"] == 1
    assert report["runtime"]["python_version"]
    assert report["runtime"]["machine"]
    assert report["runtime"]["process_architecture_bits"] in (32, 64)
    assert report["device_probes"]["display"] == "not_run"
    assert report["device_probes"]["audio"] == "not_run"
    assert report["device_probes"]["joystick"] == "not_run"


def test_report_continues_when_package_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def module_found(module_name: str) -> object:
        return object() if module_name == "pygame" else None

    def package_version(distribution_name: str) -> str:
        if distribution_name == "pygame":
            raise importlib.metadata.PackageNotFoundError(distribution_name)
        if distribution_name == "pymunk":
            raise importlib.metadata.PackageNotFoundError(distribution_name)
        return "1.0"

    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", module_found)
    monkeypatch.setattr(diagnostics.importlib.metadata, "version", package_version)

    report = diagnostics.collect_report()

    assert report["libraries"]["runtime"]["pygame"]["status"] == (
        "module_found_version_unknown"
    )
    assert report["libraries"]["runtime"]["pymunk"]["status"] == "missing"


def test_package_inspection_reports_partial_metadata_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda _name: None)

    def failed_metadata(_name: str) -> str:
        raise RuntimeError("details are deliberately omitted")

    monkeypatch.setattr(diagnostics.importlib.metadata, "version", failed_metadata)

    result = diagnostics.inspect_library("unknown_module", "unknown_distribution")

    assert result["status"] == "inspection_partial"
    assert result["metadata_error_type"] == "RuntimeError"
    assert "details are deliberately omitted" not in json.dumps(result)


def test_cli_outputs_json_without_importing_pygame_or_reading_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUika_DIAGNOSTICS_SENTINEL", "do-not-print-this-value")
    script = Path(diagnostics.__file__).resolve()
    runner = (
        "import importlib.util, json, sys; "
        f"spec = importlib.util.spec_from_file_location('diagnostics', {str(script)!r}); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "module.main(['--format', 'json']); "
        "print('DIAG_FLAGS=' + json.dumps({'pygame_loaded': any("
        "name == 'pygame' or name.startswith('pygame.') for name in sys.modules)}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", runner],
        capture_output=True,
        check=False,
        text=True,
        env=os.environ.copy(),
    )

    assert result.returncode == 0, result.stderr
    output, marker, flags_json = result.stdout.partition("DIAG_FLAGS=")
    assert marker
    report = json.loads(output)
    assert report["report_version"] == 1
    assert "do-not-print-this-value" not in result.stdout
    assert json.loads(flags_json)["pygame_loaded"] is False


def test_text_report_is_readable() -> None:
    text_report = diagnostics.format_text(diagnostics.collect_report())

    assert "Suika Elika environment report" in text_report
    assert "Architecture:" in text_report
    assert "Device probes: not run" in text_report
