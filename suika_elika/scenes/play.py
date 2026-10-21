"""Gameplay scene façade: fixed simulation steps and snapshot-based drawing."""

from __future__ import annotations

from math import isfinite
from typing import Protocol

from suika_elika.contracts import (
    CanvasPort,
    DomainEvent,
    InputAction,
    InputEdgeQueue,
    InputFrame,
    RoundState,
    SceneTransition,
    SessionSnapshot,
)
from suika_elika.game.session import GameSession


class PresentationCanvas(CanvasPort, Protocol):
    """Optional presentation hooks implemented by the concrete Pygame renderer."""

    def advance_presentation(
        self, delta_seconds: float, events: tuple[DomainEvent, ...] = ()
    ) -> None: ...

    def set_round_metrics(
        self,
        *,
        best_fruit_level: int,
        watermelons: int,
        duration_seconds: float,
    ) -> None: ...


class PlayScene:
    """Queue render-frame actions, step the session at fixed cadence, and draw it.

    The application calls ``simulation_step`` zero or more times from its fixed
    accumulator. UI ``update`` advances only presentation effects.
    """

    def __init__(self, session: GameSession) -> None:
        self.session = session
        self._edges = InputEdgeQueue()
        self._move_x = 0.0
        self._fine_adjust = False
        self._scene_transition_pending = False
        self._presentation_canvas: object | None = None

    @property
    def snapshot(self) -> SessionSnapshot:
        return self.session.snapshot

    def enter(self) -> None:
        self._edges.clear()
        self._move_x = 0.0
        self._fine_adjust = False
        self._scene_transition_pending = False
        self._presentation_canvas = None

    def exit(self) -> None:
        self._edges.clear()
        self._move_x = 0.0
        self._fine_adjust = False

    def handle_actions(self, frame: InputFrame) -> SceneTransition | None:
        if any(edge.action is InputAction.PAUSE for edge in frame.edges):
            if self.session.round_state is RoundState.GAME_OVER:
                return None
            self._edges.clear()
            self._move_x = 0.0
            self._fine_adjust = False
            self.session.pause()
            self._scene_transition_pending = True
            return SceneTransition("pause")

        for edge in frame.edges:
            if edge.action is not InputAction.PAUSE:
                self._edges.enqueue(edge)
        self._move_x = frame.move_x
        self._fine_adjust = frame.fine_adjust
        return None

    def simulation_step(
        self, *, launch_contacted: bool = False
    ) -> tuple[DomainEvent, ...]:
        """Advance exactly one GameSession fixed step with queued input edges."""
        if self._scene_transition_pending and self.session.round_state is not RoundState.PAUSED:
            self._scene_transition_pending = False
        if self._scene_transition_pending or self.session.round_state in (
            RoundState.PAUSED,
            RoundState.GAME_OVER,
        ):
            self._edges.clear()
            return ()
        frame = InputFrame(
            move_x=self._move_x,
            fine_adjust=self._fine_adjust,
            edges=self._edges.consume_for_step(),
        )
        return self.session.step(frame, launch_contacted=launch_contacted)

    def update(self, delta_seconds: float) -> SceneTransition | None:
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("UI delta must be finite and non-negative")
        if self._presentation_canvas is not None:
            self.advance_presentation(self._presentation_canvas, delta_seconds)
        if self.session.round_state is RoundState.GAME_OVER:
            return SceneTransition(
                "results",
                self._result_summary(),
            )
        return None

    def draw(self, canvas: CanvasPort) -> None:
        self._presentation_canvas = canvas
        setter = getattr(canvas, "set_round_metrics", None)
        if callable(setter):
            setter(
                best_fruit_level=self.session.best_fruit_level,
                watermelons=self.session.watermelons,
                duration_seconds=self.session.duration_seconds,
            )
        canvas.draw_session(self.session.snapshot, self.session.events)

    def advance_presentation(self, canvas: object, delta_seconds: float) -> None:
        advance = getattr(canvas, "advance_presentation", None)
        if callable(advance):
            advance(delta_seconds, self.session.events)

    def _result_summary(self) -> tuple[tuple[str, int | float], ...]:
        return (
            ("score", self.session.score),
            ("high_score", self.session.high_score),
            ("best_fruit_level", self.session.best_fruit_level),
            ("watermelons", self.session.watermelons),
            ("duration_seconds", self.session.duration_seconds),
        )


__all__ = ["PlayScene", "PresentationCanvas"]
