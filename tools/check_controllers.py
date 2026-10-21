"""Mostra no terminal os joysticks que o Pygame/SDL consegue enumerar."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections.abc import Sequence
from typing import Any


def collect_controllers(pygame: Any) -> dict[str, Any]:
    """Probe native joysticks without opening a game window or starting audio."""
    devices: list[dict[str, Any]] = []
    errors: list[str] = []
    controller_api = None
    try:
        pygame.display.init()
        pygame.joystick.init()
        try:
            controller_api = importlib.import_module("pygame._sdl2.controller")
            controller_api.init()
        except (ImportError, AttributeError, pygame.error):
            controller_api = None
        pygame.event.pump()
        count = pygame.joystick.get_count()
        for index in range(count):
            joystick = None
            try:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                devices.append(
                    {
                        "index": index,
                        "instance_id": joystick.get_instance_id(),
                        "name": joystick.get_name(),
                        "guid": joystick.get_guid(),
                        "axes": joystick.get_numaxes(),
                        "buttons": joystick.get_numbuttons(),
                        "hats": joystick.get_numhats(),
                        "sdl_mapped": (
                            bool(controller_api.is_controller(index)) if controller_api else None
                        ),
                    }
                )
            except Exception as error:
                errors.append(f"Índice {index}: {error}")
            finally:
                if joystick is not None:
                    joystick.quit()
        return {
            "pygame_version": pygame.version.ver,
            "sdl_version": list(pygame.get_sdl_version()),
            "joystick_count": count,
            "opened_count": len(devices),
            "keyboard_counted": False,
            "devices": devices,
            "errors": errors,
        }
    finally:
        if controller_api is not None:
            controller_api.quit()
        pygame.joystick.quit()
        pygame.display.quit()


def format_text(report: dict[str, Any]) -> str:
    lines = [
        f"Pygame {report['pygame_version']} · SDL {'.'.join(map(str, report['sdl_version']))}",
        f"Controles/joysticks que o Pygame vê: {report['joystick_count']}",
        "Teclado comum: não entra nessa contagem. Pads virtuais do SDL podem aparecer.",
    ]
    for device in report["devices"]:
        mapped = {True: "sim", False: "não", None: "API indisponível"}[device["sdl_mapped"]]
        lines.extend(
            [
                f"  índice {device['index']}: {device['name']}",
                f"    instance_id={device['instance_id']}  GUID={device['guid']}",
                f"    eixos={device['axes']}  botões={device['buttons']}  hats={device['hats']}",
                f"    mapeamento SDL Controller: {mapped}",
            ]
        )
    lines.extend(f"ERRO: {error}" for error in report["errors"])
    lines.append("Índices são desta enumeração e podem mudar após conectar/remover controles.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="usar driver de vídeo dummy para executar por SSH/terminal sem display",
    )
    args = parser.parse_args(argv)
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    try:
        pygame = importlib.import_module("pygame")
        report = collect_controllers(pygame)
    except Exception as error:
        print(f"Não foi possível consultar os controles: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.format == "json"
        else format_text(report)
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
