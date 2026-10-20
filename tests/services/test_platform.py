from __future__ import annotations

from pathlib import Path

from suika_elika.platform import UserPaths, resolve_user_paths


def test_windows_paths_use_application_roots(tmp_path: Path) -> None:
    roaming = tmp_path / "roaming"
    local = tmp_path / "local"
    paths = resolve_user_paths(
        system="Windows",
        environment={"APPDATA": str(roaming), "LOCALAPPDATA": str(local)},
        home=tmp_path,
        batocera=False,
    )

    assert paths.config_dir == roaming / "SuikaElika"
    assert paths.data_dir == local / "SuikaElika"
    assert paths.log_dir == paths.config_dir / "logs"


def test_linux_uses_absolute_xdg_directories_and_fallbacks(tmp_path: Path) -> None:
    xdg_config = tmp_path / "xdg-config"
    xdg_data = tmp_path / "xdg-data"
    paths = resolve_user_paths(
        system="Linux",
        environment={"XDG_CONFIG_HOME": str(xdg_config), "XDG_DATA_HOME": str(xdg_data)},
        home=tmp_path,
        batocera=False,
    )
    assert paths.config_dir == xdg_config / "suika-elika"
    assert paths.data_dir == xdg_data / "suika-elika"

    fallback = resolve_user_paths(
        system="Linux",
        environment={"XDG_CONFIG_HOME": "relative/config", "XDG_DATA_HOME": "relative/data"},
        home=tmp_path,
        batocera=False,
    )
    assert fallback.config_dir == tmp_path / ".config" / "suika-elika"
    assert fallback.data_dir == tmp_path / ".local" / "share" / "suika-elika"


def test_batocera_paths_and_explicit_overrides(tmp_path: Path) -> None:
    paths = resolve_user_paths(system="Linux", batocera=True)
    assert paths.config_dir == Path("/userdata/system/configs/suika-elika")
    assert paths.data_dir == Path("/userdata/saves/suika-elika")

    overridden = resolve_user_paths(
        system="Linux",
        batocera=True,
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
    )
    assert overridden == UserPaths(
        tmp_path / "config", tmp_path / "data", tmp_path / "logs"
    )
    assert overridden.create_directories() == ()
    assert all(
        path.is_dir()
        for path in (overridden.config_dir, overridden.data_dir, overridden.log_dir)
    )
