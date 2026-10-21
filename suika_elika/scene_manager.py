"""Scene routing and lifecycle for one local game application."""

from __future__ import annotations

from typing import Any

from suika_elika.audio import NullAudioManager
from suika_elika.contracts import (
    AudioPort,
    DomainEvent,
    InputFrame,
    PersistencePort,
    SceneTransition,
)
from suika_elika.game.session import GameSession
from suika_elika.input.manager import InputManager
from suika_elika.input.profiles import ProfileRepository
from suika_elika.scenes.help import HelpScene
from suika_elika.scenes.options import OptionsScene
from suika_elika.scenes.pause import PauseScene
from suika_elika.scenes.play import PlayScene
from suika_elika.scenes.results import ResultsScene, ResultSummary
from suika_elika.scenes.title import TitleScene


class SceneManager:
    """Own scene transitions while keeping application services injected."""

    def __init__(
        self,
        session: GameSession,
        persistence: PersistencePort,
        input_manager: InputManager,
        audio: AudioPort | None = None,
        *,
        controller_status: str = "Controle não conectado",
    ) -> None:
        self.session = session
        self.persistence = persistence
        self.input_manager = input_manager
        self.audio = audio or NullAudioManager()
        self.controller_status = controller_status
        self.profile_repository = ProfileRepository(persistence)
        self.play_scene = PlayScene(session)
        self._current_name = "title"
        # Menu and gameplay scenes use two compatible draw-port specializations.
        self.current: Any = self._make_scene("title")
        self.current.enter()
        self.running = True

    @property
    def current_name(self) -> str:
        return self._current_name

    def handle_actions(self, frame: InputFrame) -> None:
        """Route one render-frame input snapshot and apply any transition."""
        transition = self.current.handle_actions(frame)
        if transition is not None:
            self.transition(transition)

    def update(self, delta_seconds: float) -> None:
        transition = self.current.update(delta_seconds)
        if transition is not None:
            self.transition(transition)

    def transition(self, transition: SceneTransition) -> None:
        destination = transition.destination
        if destination == "exit":
            self.current.exit()
            self.running = False
            return
        if destination == "paused":
            destination = "pause"

        payload = dict(transition.payload)
        if destination == "play":
            if payload.get("resume") is True:
                self.session.resume()
                self.audio.resume()
            elif payload.get("restart") is True or self._current_name != "pause":
                self.session.restart()
                self.audio.resume()
        elif destination == "title" and payload.get("abandoned") is True:
            self.session.restart()
            self.audio.resume()
        elif destination == "options" and payload.get("return_to") == "paused":
            pass

        next_scene = self._make_scene(destination, payload)
        self.current.exit()
        self.current = next_scene
        self._current_name = destination
        self.current.enter()

    def simulation_step(self) -> tuple[DomainEvent, ...]:
        """Advance the active game scene once and send its copied events to audio."""
        if self._current_name != "play":
            return ()
        events = self.play_scene.simulation_step()
        self.audio.consume(events)
        return events

    def reset_input(self) -> None:
        self.input_manager.reset()
        if self._current_name == "play":
            self.play_scene.exit()
            self.play_scene.enter()

    def _make_scene(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        values = payload or {}
        if name == "title":
            return TitleScene(controller_status=self.controller_status)
        if name == "play":
            return self.play_scene
        if name == "help":
            return HelpScene(return_to=str(values.get("return_to", "title")))
        if name == "options":
            return OptionsScene(
                self.persistence,
                return_to=str(values.get("return_to", "title")),
                profile_repository=self.profile_repository,
            )
        if name == "pause":
            self.audio.pause()
            return PauseScene()
        if name == "results":
            return ResultsScene(self._result_summary(values))
        raise ValueError(f"unknown scene destination: {name}")

    def _result_summary(self, payload: dict[str, Any]) -> ResultSummary:
        snapshot = self.session.snapshot
        return ResultSummary(
            score=int(payload.get("score", snapshot.score)),
            high_score=int(payload.get("high_score", snapshot.high_score)),
            best_fruit_level=int(payload.get("best_fruit_level", self.session.best_fruit_level)),
            watermelons=int(payload.get("watermelons", self.session.watermelons)),
            duration_seconds=float(payload.get("duration_seconds", self.session.duration_seconds)),
        )


__all__ = ["SceneManager"]
