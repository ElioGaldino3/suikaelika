"""Pause menu with explicit confirmations for restart and abandoning a run."""

from __future__ import annotations

from suika_elika.contracts import InputAction, InputFrame, SceneTransition

from .title import MenuItem, MenuScene, MenuSnapshot


class PauseScene(MenuScene):
    """Pause choices; destructive actions open a dialog focused on Cancel."""

    def __init__(self, *, play_destination: str = "play") -> None:
        self.play_destination = play_destination
        super().__init__(
            "Pausado",
            (
                MenuItem("Continuar", play_destination, (("resume", True),)),
                MenuItem("Reiniciar", "restart"),
                MenuItem("Opções", "options", (("return_to", "paused"),)),
                MenuItem("Voltar ao menu", "abandon"),
            ),
        )
        self.confirmation: str | None = None
        self._confirm_index = 1

    @property
    def snapshot(self) -> MenuSnapshot:
        if self.confirmation is None:
            return super().snapshot
        action = "reiniciar a partida" if self.confirmation == "restart" else "abandonar a partida"
        return MenuSnapshot(
            "Confirmar ação",
            ("Sim", "Cancelar"),
            self._confirm_index,
            subtitle=f"Deseja {action}?",
            footer="Cancelar fica selecionado para proteger a partida.",
        )

    def handle_actions(self, frame: InputFrame) -> SceneTransition | None:
        if self.confirmation is not None:
            for edge in self._fresh_edges(frame):
                if edge.action is InputAction.NAV_UP or edge.action is InputAction.NAV_DOWN:
                    self._confirm_index = 1 - self._confirm_index
                elif edge.action is InputAction.CANCEL:
                    self.confirmation = None
                    self.selected_index = 0
                    return None
                elif edge.action is InputAction.CONFIRM:
                    if self._confirm_index == 1:
                        self.confirmation = None
                        self.selected_index = 0
                        return None
                    action = self.confirmation
                    self.confirmation = None
                    if action == "restart":
                        return SceneTransition(self.play_destination, (("restart", True),))
                    return SceneTransition("title", (("abandoned", True),))
            return None

        for edge in self._fresh_edges(frame):
            if edge.action is InputAction.NAV_UP:
                self.selected_index = (self.selected_index - 1) % len(self.items)
            elif edge.action is InputAction.NAV_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.items)
            elif edge.action is InputAction.CANCEL:
                return SceneTransition(self.play_destination, (("resume", True),))
            elif edge.action is InputAction.CONFIRM:
                item = self.items[self.selected_index]
                if item.destination in {"restart", "abandon"}:
                    self.confirmation = item.destination
                    self._confirm_index = 1
                    return None
                return self._choose(item)
        return None


__all__ = ["PauseScene"]
