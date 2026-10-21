"""Title menu and small Pygame-free menu presentation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from suika_elika.contracts import InputAction, InputEdge, InputFrame, SceneTransition


@dataclass(frozen=True, slots=True)
class MenuItem:
    """One visible choice and its scene transition target."""

    label: str
    destination: str
    payload: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.label or not self.destination:
            raise ValueError("menu labels and destinations must not be empty")


@dataclass(frozen=True, slots=True)
class MenuSnapshot:
    """Immutable text and focus state passed to a concrete renderer."""

    title: str
    choices: tuple[str, ...]
    selected_index: int
    subtitle: str = ""
    footer: str = ""
    message: str = ""
    disabled_indices: tuple[int, ...] = ()


class MenuCanvas(Protocol):
    """Presentation adapter for menus; scenes do not import a graphics library."""

    def draw_menu(self, snapshot: MenuSnapshot) -> None: ...


class MenuScene:
    """Shared action-only focus navigation for menu scenes."""

    def __init__(
        self,
        title: str,
        items: tuple[MenuItem, ...],
        *,
        subtitle: str = "",
        footer: str = "↑/↓ Navegar  ·  botão sul Confirmar  ·  botão leste Voltar",
        cancel_destination: str | None = None,
        cancel_payload: tuple[tuple[str, str | int | float | bool | None], ...] = (),
    ) -> None:
        if not title or not items:
            raise ValueError("menu title and at least one item are required")
        self.title = title
        self.items = items
        self.subtitle = subtitle
        self.footer = footer
        self.cancel_destination = cancel_destination
        self.cancel_payload = cancel_payload
        self.selected_index = 0
        self.message = ""
        self._last_edge_sequence = -1

    @property
    def snapshot(self) -> MenuSnapshot:
        return MenuSnapshot(
            self.title,
            tuple(item.label for item in self.items),
            self.selected_index,
            self.subtitle,
            self.footer,
            self.message,
            tuple(index for index, item in enumerate(self.items) if not item.enabled),
        )

    def enter(self) -> None:
        pass

    def exit(self) -> None:
        pass

    def update(self, delta_seconds: float) -> SceneTransition | None:
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("UI delta must be finite and non-negative")
        return None

    def draw(self, canvas: MenuCanvas) -> None:
        canvas.draw_menu(self.snapshot)

    def _fresh_edges(self, frame: InputFrame) -> tuple[InputEdge, ...]:
        fresh = tuple(edge for edge in frame.edges if edge.sequence > self._last_edge_sequence)
        if fresh:
            self._last_edge_sequence = fresh[-1].sequence
        return fresh

    def handle_actions(self, frame: InputFrame) -> SceneTransition | None:
        for edge in self._fresh_edges(frame):
            if edge.action is InputAction.NAV_UP:
                self.selected_index = (self.selected_index - 1) % len(self.items)
            elif edge.action is InputAction.NAV_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.items)
            elif edge.action is InputAction.CONFIRM:
                return self._choose(self.items[self.selected_index])
            elif edge.action is InputAction.CANCEL and self.cancel_destination:
                return SceneTransition(self.cancel_destination, self.cancel_payload)
        return None

    def _choose(self, item: MenuItem) -> SceneTransition | None:
        if not item.enabled:
            self.message = "Conecte dois controles para jogar BATALHA."
            return None
        return SceneTransition(item.destination, item.payload)


class TitleScene(MenuScene):
    """Landing menu with physical-position instructions and device status."""

    def __init__(
        self, *, controller_status: str = "Controle não conectado", battle_ready: bool = False
    ) -> None:
        super().__init__(
            "Suika Elika",
            (
                MenuItem("Jogar", "play"),
                MenuItem("BATALHA", "battle", enabled=battle_ready),
                MenuItem("Como jogar", "help", (("return_to", "title"),)),
                MenuItem("Opções", "options", (("return_to", "title"),)),
                MenuItem("Sair", "exit"),
            ),
            subtitle=f"{controller_status} · BATALHA: 2 controles · meta de 500 pontos",
            footer=(
                "Mover: direcional  ·  Confirmar/Soltar: botão sul "
                "(A Xbox, B Nintendo, cruz PlayStation)"
            ),
        )


__all__ = ["MenuCanvas", "MenuItem", "MenuScene", "MenuSnapshot", "TitleScene"]
