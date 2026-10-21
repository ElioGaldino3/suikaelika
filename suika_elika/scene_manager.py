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
from suika_elika.game.battle import BattleSession
from suika_elika.game.session import GameSession
from suika_elika.input.manager import InputManager
from suika_elika.input.profiles import ProfileRepository
from suika_elika.scenes.battle import BattleResultsScene, BattleScene
from suika_elika.scenes.help import HelpScene
from suika_elika.scenes.options import OptionsScene
from suika_elika.scenes.pause import PauseScene
from suika_elika.scenes.play import PlayScene
from suika_elika.scenes.results import ResultsScene, ResultSummary
from suika_elika.scenes.title import MenuItem, TitleScene


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
        fixed_dt: float = 1 / 120,
        keyboard_enabled: bool = False,
    ) -> None:
        self.session = session
        self.persistence = persistence
        self.input_manager = input_manager
        self.audio = audio or NullAudioManager()
        self.controller_status = controller_status
        self.keyboard_enabled = keyboard_enabled
        self.battle_ready = False
        self.battle_mode = False
        self.battle_session = BattleSession(fixed_dt=fixed_dt)
        self.battle_scene = BattleScene(self.battle_session)
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

    def set_controller_count(self, count: int) -> None:
        was_ready = self.battle_ready
        self.battle_ready = count >= 2
        self.controller_status = f"{count} controle(s) conectado(s)"
        if count == 0:
            self.controller_status += (
                " · teclado desktop" if self.keyboard_enabled else " · conecte um controle"
            )
        if isinstance(self.current, TitleScene):
            if self.battle_ready and not was_ready:
                self.current.message = ""
            self.current.items = tuple(
                MenuItem(item.label, item.destination, item.payload,
                         self.battle_ready if item.destination == "battle" else item.enabled)
                for item in self.current.items
            )
            self.current.subtitle = (
                f"{self.controller_status} · BATALHA: 2 controles · meta de 500 pontos"
            )
        elif isinstance(self.current, BattleResultsScene):
            self.current.items = (
                MenuItem("Revanche", "battle", (("restart", True),), self.battle_ready),
                MenuItem("Menu", "title"),
            )

    def handle_battle_actions(self, frames: tuple[InputFrame, InputFrame]) -> None:
        if self._current_name == "battle":
            transition = self.battle_scene.handle_players(frames)
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
        if destination == "battle":
            if not self.battle_ready:
                return
            if payload.get("resume") is True:
                self.battle_session.resume()
            else:
                self.battle_session.restart()
            self.battle_mode = True
            self.audio.resume()
        if destination == "play":
            self.battle_mode = False
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
        if destination == "title":
            self.battle_mode = False
            self.audio.resume()

        next_scene = self._make_scene(destination, payload)
        self.current.exit()
        self.current = next_scene
        self._current_name = destination
        self.current.enter()

    def simulation_step(self) -> tuple[DomainEvent, ...]:
        """Advance the active game scene once and send its copied events to audio."""
        if self._current_name == "battle":
            events = self.battle_scene.simulation_step()
            self.audio.consume(events)
            return events
        if self._current_name != "play":
            return ()
        events = self.play_scene.simulation_step()
        self.audio.consume(events)
        return events

    def reset_input(self) -> None:
        self.input_manager.reset()
        self.battle_scene.exit()
        if self._current_name == "play":
            self.play_scene.exit()
            self.play_scene.enter()

    def _make_scene(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        values = payload or {}
        if name == "title":
            return TitleScene(
                controller_status=self.controller_status, battle_ready=self.battle_ready
            )
        if name == "battle":
            return self.battle_scene
        if name == "battle_results":
            return BattleResultsScene(self.battle_session.snapshot, ready=self.battle_ready)
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
            return PauseScene(play_destination="battle" if self.battle_mode else "play")
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
