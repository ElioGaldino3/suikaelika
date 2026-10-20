"""Portable user data locations for development and Batocera."""

from __future__ import annotations

import os
import platform as host_platform
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UserPaths:
    """Resolved writable directories for settings, saved data, and logs."""

    config_dir: Path
    data_dir: Path
    log_dir: Path

    def create_directories(self) -> tuple[Path, ...]:
        """Create each directory, returning paths whose creation failed."""
        failures: list[Path] = []
        for directory in (self.config_dir, self.data_dir, self.log_dir):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                failures.append(directory)
        return tuple(failures)


def _absolute_env_path(
    environment: Mapping[str, str], key: str, fallback: Path
) -> Path:
    value = environment.get(key)
    if value:
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
    return fallback


def resolve_user_paths(
    *,
    config_dir: str | Path | None = None,
    data_dir: str | Path | None = None,
    log_dir: str | Path | None = None,
    system: str | None = None,
    environment: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    batocera: bool | None = None,
) -> UserPaths:
    """Resolve project paths, with explicit directory overrides taking priority.

    ``batocera`` is injectable for tests and portable launchers. If omitted,
    Batocera is detected from the standard ``/userdata`` mount on Linux.
    """
    current_system = system or host_platform.system()
    env = os.environ if environment is None else environment
    home_path = Path(home).expanduser() if home is not None else Path.home()
    is_batocera = batocera
    if is_batocera is None:
        is_batocera = current_system == "Linux" and Path("/userdata").is_dir()

    if is_batocera:
        default_config = Path("/userdata/system/configs/suika-elika")
        default_data = Path("/userdata/saves/suika-elika")
    elif current_system == "Windows":
        default_config = _absolute_env_path(
            env, "APPDATA", home_path / "AppData" / "Roaming"
        ) / "SuikaElika"
        default_data = _absolute_env_path(
            env, "LOCALAPPDATA", home_path / "AppData" / "Local"
        ) / "SuikaElika"
    else:
        default_config = _absolute_env_path(
            env, "XDG_CONFIG_HOME", home_path / ".config"
        ) / "suika-elika"
        default_data = _absolute_env_path(
            env, "XDG_DATA_HOME", home_path / ".local" / "share"
        ) / "suika-elika"

    resolved_config = Path(config_dir).expanduser() if config_dir is not None else default_config
    resolved_data = Path(data_dir).expanduser() if data_dir is not None else default_data
    resolved_log = Path(log_dir).expanduser() if log_dir is not None else resolved_config / "logs"
    return UserPaths(resolved_config, resolved_data, resolved_log)
