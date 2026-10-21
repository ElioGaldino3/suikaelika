"""Local checks for the Pygame package prepared for Batocera."""

from pathlib import Path

import pytest

from tools.build_batocera import build_package

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


def test_build_creates_and_replaces_the_pygame_installation_folder(tmp_path: Path) -> None:
    for directory in ("suika_elika", "data", "assets"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "marker").write_text(directory, encoding="utf-8")
    cache = tmp_path / "suika_elika" / "__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"cache")
    entrypoint = tmp_path / "packaging" / "batocera" / "pygame" / "SuikaElika.pygame"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("print('run')\n", encoding="utf-8")

    output = build_package(tmp_path)
    (output / "stale-file").write_text("old", encoding="utf-8")
    output = build_package(tmp_path)

    assert output == tmp_path / "dist" / "SuikaElika"
    assert (output / "SuikaElika.pygame").read_text(encoding="utf-8") == "print('run')\n"
    for directory in ("suika_elika", "data", "assets"):
        assert (output / directory / "marker").is_file()
    assert (output / "README-BATOCERA.txt").is_file()
    assert not (output / "stale-file").exists()
    assert not (output / "suika_elika" / "__pycache__").exists()


def test_build_rejects_output_outside_dist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside the project's dist"):
        build_package(tmp_path, tmp_path / "outside")


def test_installation_instructions_cover_pygame_and_limits() -> None:
    instructions = " ".join(
        (ROOT / "docs" / "BATOCERA.md").read_text(encoding="utf-8").split()
    )

    assert "/userdata/roms/pygame" in instructions
    assert "dist/SuikaElika" in instructions
    assert "SuikaElika.pygame" in instructions
    assert "python3" in instructions
    assert "Pygame" in instructions
    assert "Pymunk" in instructions
    assert "joystick" in instructions.casefold()
    assert "não comprovam compatibilidade" in instructions.casefold()
    assert "ports" not in instructions.casefold()
    assert "diagnostics.py" in instructions
