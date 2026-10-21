"""Battle gameplay scene with separate input queues and a shared pause."""

from __future__ import annotations

from math import isfinite
from typing import Protocol

from suika_elika.contracts import (
    DomainEvent,
    InputAction,
    InputEdgeQueue,
    InputFrame,
    SceneTransition,
)
from suika_elika.game.battle import BattleSession, BattleSnapshot
from suika_elika.scenes.title import MenuItem, MenuScene


class BattleCanvas(Protocol):
    def draw_battle(self, snapshot: BattleSnapshot) -> None: ...


class BattleScene:
    def __init__(self, session: BattleSession) -> None:
        self.session = session
        self._queues = (InputEdgeQueue(), InputEdgeQueue())
        self._frames = (InputFrame(), InputFrame())

    def enter(self) -> None:
        self.exit()

    def exit(self) -> None:
        for queue in self._queues:
            queue.clear()
        self._frames = (InputFrame(), InputFrame())

    def handle_players(self, frames: tuple[InputFrame, InputFrame]) -> SceneTransition | None:
        if any(edge.action is InputAction.PAUSE for f in frames for edge in f.edges):
            self.session.pause()
            self.exit()
            return SceneTransition("pause")
        for queue, frame in zip(self._queues, frames, strict=True):
            queue.enqueue_frame(frame)
        self._frames = frames
        return None

    def simulation_step(self) -> tuple[DomainEvent, ...]:
        frames = tuple(
            InputFrame(
                move_x=frame.move_x, fine_adjust=frame.fine_adjust, edges=queue.consume_for_step(),
                drop_held=frame.drop_held,
            )
            for frame, queue in zip(self._frames, self._queues, strict=True)
        )
        return self.session.step((frames[0], frames[1]))

    def update(self, delta_seconds: float) -> SceneTransition | None:
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("UI delta must be finite and non-negative")
        return SceneTransition("battle_results") if self.session.finished else None

    def draw(self, canvas: BattleCanvas) -> None:
        canvas.draw_battle(self.session.snapshot)


class BattleResultsScene(MenuScene):
    def __init__(self, snapshot: BattleSnapshot, *, ready: bool) -> None:
        title = "Empate!" if snapshot.winner is None else f"Jogador {snapshot.winner} venceu!"
        reason = (
            "Limite da cesta ultrapassado"
            if snapshot.reason == "overflow"
            else "Meta de 500 pontos alcançada"
        )
        super().__init__(
            title,
            (
                MenuItem("Revanche", "battle", (("restart", True),), enabled=ready),
                MenuItem("Menu", "title"),
            ),
            subtitle=(
                f"{reason}\nJogador 1: {snapshot.players[0].score} pontos"
                f" · Jogador 2: {snapshot.players[1].score} pontos"
            ),
            cancel_destination="title",
        )
