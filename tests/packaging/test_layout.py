"""Local checks for the source-tree launchers prepared for Batocera."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "packaging" / "batocera"


def test_pygame_entrypoint_bootstraps_package_from_its_install_directory() -> None:
    entrypoint = PACKAGING / "pygame" / "SuikaElika.pygame"
    source = entrypoint.read_text(encoding="utf-8")

    compile(source, str(entrypoint), "exec")
    assert source.startswith("#!/usr/bin/env python3\n")
    assert "INSTALL_ROOT = Path(__file__).resolve().parent" in source
    assert "sys.path.insert(0, str(INSTALL_ROOT))" in source
    assert 'importlib.import_module("suika_elika.app").main' in source
    assert "raise SystemExit(main())" in source
    assert (ROOT / "suika_elika" / "app.py").is_file()
    assert (ROOT / "data" / "rules" / "classic-v2.json").is_file()
    assert (ROOT / "assets" / "sprites" / "cherry.png").is_file()
    assert (ROOT / "assets" / "backgrounds" / "gameplay.png").is_file()


def test_ports_launcher_uses_hidden_data_folder_quotes_paths_and_exec() -> None:
    launcher = PACKAGING / "ports" / "Suika Elika.sh"
    raw = launcher.read_bytes()
    source = raw.decode("utf-8")

    assert b"\r" not in raw
    assert source.startswith("#!/bin/sh\n")
    assert '"$(dirname -- "$0")"' in source
    assert '"$PORTS_DIR/.data/SuikaElika"' in source
    assert 'PYTHON="${SUIKA_ELIKA_PYTHON:-python3}"' in source
    assert '"$PYTHON" "$GAME_DIR/SuikaElika.pygame" "$@"' in source
    assert "exec " in source
    assert "SDL_" not in source
    assert "export DISPLAY" not in source


def test_installation_instructions_cover_both_launch_modes_and_limits() -> None:
    instructions = " ".join(
        (ROOT / "docs" / "BATOCERA.md").read_text(encoding="utf-8").split()
    )

    assert "/userdata/roms/pygame" in instructions
    assert "/userdata/roms/ports/.data/SuikaElika" in instructions
    assert "python3" in instructions
    assert "Pygame" in instructions
    assert "Pymunk" in instructions
    assert "jogador 1" in instructions
    assert "mesma identidade GUID/nome" in instructions
    assert "não foi homologada" in instructions.casefold()
    assert '"$PROJECT_ROOT/assets"' in instructions
