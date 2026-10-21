"""Install the physics dependency into Batocera's persistent user storage."""

from __future__ import annotations

import importlib
import os
import site
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

PYMUNK_REQUIREMENT = "pymunk>=7.3,<8"
PIP_BOOTSTRAP_URL = "https://bootstrap.pypa.io/get-pip.py"
USER_DATA = Path("/userdata/system/configs/suika-elika")
DEPENDENCIES = USER_DATA / "python-packages"
USER_BASE = USER_DATA / "python-userbase"


def ensure_pymunk() -> None:
    """Import Pymunk, installing it with pip into writable persistent storage if needed."""
    DEPENDENCIES.mkdir(parents=True, exist_ok=True)
    site.addsitedir(str(DEPENDENCIES))
    try:
        importlib.import_module("pymunk")
        return
    except (ImportError, OSError):
        pass

    environment = os.environ.copy()
    environment["PYTHONUSERBASE"] = str(USER_BASE)
    try:
        _ensure_pip(environment)
        print("Suika Elika: instalando Pymunk (primeira execução)...", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-warn-script-location",
                "--target",
                str(DEPENDENCIES),
                PYMUNK_REQUIREMENT,
            ],
            check=True,
            env=environment,
        )
        site.addsitedir(str(DEPENDENCIES))
        importlib.invalidate_caches()
        importlib.import_module("pymunk")
        print("Suika Elika: Pymunk instalado.", flush=True)
    except Exception as error:
        raise RuntimeError(
            "Não foi possível instalar o Pymunk automaticamente. "
            "Verifique a conexão com a internet, o espaço livre e a compatibilidade "
            "do Python do Batocera. A dependência foi tentada em "
            f"{DEPENDENCIES}. Detalhe: {error}"
        ) from error


def _ensure_pip(environment: dict[str, str]) -> None:
    """Use an existing pip, ensurepip, or PyPA's bootstrap script in that order."""
    command = [sys.executable, "-m", "pip", "--version"]
    if subprocess.run(command, env=environment, capture_output=True).returncode == 0:
        return

    print("Suika Elika: preparando pip...", flush=True)
    ensured = subprocess.run(
        [sys.executable, "-m", "ensurepip", "--user"],
        env=environment,
        capture_output=True,
        text=True,
    )
    if ensured.returncode == 0 and subprocess.run(
        command, env=environment, capture_output=True
    ).returncode == 0:
        return

    # Batocera's Python build may omit ensurepip. In that case bootstrap pip
    # into the same user-owned base; never write to the system Python folders.
    with tempfile.TemporaryDirectory(prefix="suika-elika-pip-") as temporary:
        get_pip = Path(temporary) / "get-pip.py"
        with urlopen(PIP_BOOTSTRAP_URL, timeout=30) as response:
            get_pip.write_bytes(response.read())
        subprocess.run(
            [sys.executable, str(get_pip), "--user", "--disable-pip-version-check"],
            check=True,
            env=environment,
        )
    if subprocess.run(command, env=environment, capture_output=True).returncode != 0:
        raise RuntimeError("pip continua indisponível após a instalação.")
