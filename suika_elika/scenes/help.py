"""Short Portuguese control and gameplay guide."""

from __future__ import annotations

from suika_elika.contracts import SceneTransition

from .title import MenuItem, MenuScene


class HelpScene(MenuScene):
    """Three-step help page that returns only to its originating menu."""

    def __init__(self, *, return_to: str = "title") -> None:
        if return_to not in {"title", "options", "paused"}:
            raise ValueError("help return destination is invalid")
        super().__init__(
            "Como jogar",
            (MenuItem("Voltar", return_to),),
            subtitle=(
                "1. Mova a mira com o direcional.\n"
                "2. Botão sul: aperte para soltar; segure para repetir a 180 BPM.\n"
                "3. Combine frutas iguais e evite a linha de perigo."
            ),
            footer="Botão sul: confirmar · botão leste: voltar",
            cancel_destination=return_to,
        )

    def _choose(self, item: MenuItem) -> SceneTransition:
        return SceneTransition(item.destination)


__all__ = ["HelpScene"]
