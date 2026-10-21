"""Build the source package installed by Batocera's Pygame system."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRS = ("suika_elika", "data", "assets")
BATOCERA_PYGAME_DIR = Path("packaging") / "batocera" / "pygame"
ENTRYPOINT = BATOCERA_PYGAME_DIR / "SuikaElika.pygame"
MAIN_ENTRYPOINT = BATOCERA_PYGAME_DIR / "main.py"
PACKAGE_NAME = "SuikaElika.pygame"
INSTALL_GUIDE = """Suika Elika — Batocera Pygame build

Copy this complete folder to /userdata/roms/pygame/SuikaElika.pygame.
main.py starts the game; the nested SuikaElika.pygame file is the ROM entry point.
Neither file is a compiled binary.
Refresh the game list in EmulationStation, then launch Pygame > SuikaElika.

Batocera must provide a compatible Python, Pygame/SDL and Pymunk runtime.
"""


def build_package(
    source_root: Path = ROOT, output_dir: Path | None = None
) -> Path:
    """Copy the runtime files into a clean, ready-to-install game folder."""
    source_root = source_root.resolve()
    dist_path = source_root / "dist"
    if dist_path.is_symlink():
        raise ValueError("project dist directory must not be a symlink")
    dist_root = dist_path.resolve()
    requested_target = output_dir or dist_root / PACKAGE_NAME
    target = requested_target if requested_target.is_absolute() else source_root / requested_target
    target = target.absolute()
    if target.parent != dist_root:
        raise ValueError(
            "output directory must be inside the project's dist as a direct child"
        )
    if target.is_symlink():
        raise ValueError("output directory must not be a symlink")

    required_sources = (*PACKAGE_DIRS, str(ENTRYPOINT), str(MAIN_ENTRYPOINT))
    missing = [path for path in required_sources if not (source_root / path).exists()]
    if missing:
        raise FileNotFoundError("missing package inputs: " + ", ".join(missing))

    dist_root.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".suika-elika-build-", dir=dist_root))
    try:
        for directory in PACKAGE_DIRS:
            shutil.copytree(
                source_root / directory,
                stage / directory,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        shutil.copy2(source_root / ENTRYPOINT, stage / "SuikaElika.pygame")
        shutil.copy2(source_root / MAIN_ENTRYPOINT, stage / "main.py")
        (stage / "README-BATOCERA.txt").write_text(INSTALL_GUIDE, encoding="utf-8")

        if target.exists():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        stage.rename(target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="package folder to create (must stay inside ./dist)",
    )
    args = parser.parse_args(argv)
    output = build_package(output_dir=args.output)
    print(f"Batocera Pygame package built: {output}")
    print(f"Copy this folder to /userdata/roms/pygame/{PACKAGE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
