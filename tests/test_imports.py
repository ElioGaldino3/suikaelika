"""Import smoke checks that run in a clean interpreter."""

from __future__ import annotations

import subprocess
import sys


def test_package_imports_do_not_initialize_runtime_services() -> None:
    script = """
import importlib
import sys

for name in (
    "suika_elika",
    "suika_elika.game",
    "suika_elika.input",
    "suika_elika.rendering",
    "suika_elika.scenes",
):
    importlib.import_module(name)

assert not any(name == "pygame" or name.startswith("pygame.") for name in sys.modules)
assert not any(name.startswith("suika_elika.") for name in sys.modules if name.count(".") > 1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
