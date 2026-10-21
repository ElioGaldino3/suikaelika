"""Integration checks for scene routing and the bounded app simulation loop."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from suika_elika.app import App, calculate_menu_layout
from suika_elika.audio import NullAudioManager
from suika_elika.config import AppConfig
from suika_elika.contracts import InputAction, InputEdge, InputFrame, RoundState, SceneTransition
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.input.manager import InputBackend, InputManager, InputSample
from suika_elika.persistence import JsonPersistence
from suika_elika.platform import resolve_user_paths
from suika_elika.scene_manager import SceneManager


@pytest.fixture
def persistence(tmp_path: Path) -> JsonPersistence:
    return JsonPersistence(
        resolve_user_paths(
            config_dir=tmp_path / "config",
            data_dir=tmp_path / "data",
            log_dir=tmp_path / "logs",
            system="Linux",
            batocera=False,
        )
    )


def _stack(persistence: JsonPersistence) -> tuple[GameSession, SceneManager, NullAudioManager]:
    session = GameSession(PhysicsWorld(), persistence=persistence, seed=4)
    audio = NullAudioManager()
    manager = SceneManager(session, persistence, InputManager(), audio)
    return session, manager, audio


def _frame(sequence: int, action: InputAction) -> InputFrame:
    return InputFrame(edges=(InputEdge(sequence, action),))


def test_local_flow_starts_pauses_resumes_restarts_and_exits(persistence: JsonPersistence) -> None:
    session, manager, audio = _stack(persistence)

    manager.handle_actions(_frame(0, InputAction.CONFIRM))
    assert manager.current_name == "play"
    manager.handle_actions(_frame(1, InputAction.DROP))
    events = manager.simulation_step()
    assert session.drop_count == 1
    assert events

    manager.handle_actions(_frame(2, InputAction.PAUSE))
    assert manager.current_name == "pause"
    assert session.round_state is RoundState.PAUSED

    manager.handle_actions(_frame(3, InputAction.CONFIRM))
    assert manager.current_name == "play"
    assert session.round_state is RoundState.PLAYING
    assert audio.available is False

    manager.handle_actions(_frame(4, InputAction.PAUSE))
    manager.handle_actions(_frame(5, InputAction.NAV_DOWN))
    manager.handle_actions(_frame(6, InputAction.CONFIRM))
    assert getattr(manager.current, "confirmation", None) == "restart"
    manager.handle_actions(_frame(7, InputAction.NAV_UP))
    manager.handle_actions(_frame(8, InputAction.CONFIRM))
    assert manager.current_name == "play"
    assert session.drop_count == 0

    session._round_state = RoundState.GAME_OVER
    manager.update(0.0)
    assert manager.current_name == "results"
    manager.handle_actions(_frame(9, InputAction.CONFIRM))
    assert manager.current_name == "play"

    manager.transition(SceneTransition("exit"))
    assert not manager.running


def test_fixed_loop_caps_recovery_and_discards_backlog(persistence: JsonPersistence) -> None:
    session, manager, _audio = _stack(persistence)
    manager.transition(SceneTransition("play"))
    app = App(AppConfig(fixed_dt=0.01, max_frame_delta=0.5, max_simulation_steps=3))
    app._manager = manager

    count = app._advance_simulation(0.5)

    assert count == 3
    assert session.snapshot.round_state is RoundState.READY
    assert app.accumulator < app.config.fixed_dt


@pytest.mark.parametrize(
    ("fullscreen", "expected_size"),
    [(True, (0, 0)), (False, (1280, 720))],
)
def test_display_uses_native_resolution_for_fullscreen(
    fullscreen: bool, expected_size: tuple[int, int]
) -> None:
    calls: list[tuple[tuple[int, int], int]] = []

    class Display:
        @staticmethod
        def set_mode(size: tuple[int, int], flags: int) -> object:
            calls.append((size, flags))
            return object()

        @staticmethod
        def set_caption(_caption: str) -> None:
            pass

    pygame = SimpleNamespace(FULLSCREEN=1, display=Display())
    app = App(AppConfig(fullscreen=fullscreen), pygame_module=pygame)
    app._create_display()

    assert calls == [(expected_size, 1 if fullscreen else 0)]


def test_focus_loss_pauses_and_confirmation_resumes_without_a_drop(
    persistence: JsonPersistence,
) -> None:
    session, manager, audio = _stack(persistence)
    manager.handle_actions(_frame(0, InputAction.CONFIRM))
    manager.handle_actions(_frame(1, InputAction.DROP))
    manager.simulation_step()
    assert session.drop_count == 1

    class ConfirmAdapter:
        def poll(self) -> InputSample:
            return InputSample(action_edges=(InputAction.CONFIRM,))

    app = App()
    app._manager = manager
    app._session = session
    app._audio = audio
    app._input = manager.input_manager
    app._input.register_adapter(InputBackend.KEYBOARD_EMULATED, ConfirmAdapter())
    app._input.select_backend(InputBackend.KEYBOARD_EMULATED)

    app._lose_focus()
    assert session.round_state is RoundState.PAUSED
    app._focused = False
    app._poll_focus_confirmation(0.0, ())
    assert session.round_state is RoundState.PAUSED

    app._focused = True
    app._poll_focus_confirmation(0.0, ())
    assert session.round_state is RoundState.PLAYING
    assert session.drop_count == 1


def test_pause_options_save_and_return_to_pause(persistence: JsonPersistence) -> None:
    session, manager, _audio = _stack(persistence)
    manager.handle_actions(_frame(0, InputAction.CONFIRM))
    manager.handle_actions(_frame(1, InputAction.PAUSE))
    assert manager.current_name == "pause"

    manager.handle_actions(_frame(2, InputAction.NAV_DOWN))
    manager.handle_actions(_frame(3, InputAction.NAV_DOWN))
    manager.handle_actions(_frame(4, InputAction.CONFIRM))
    assert manager.current_name == "options"

    for sequence in range(5, 8):
        manager.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    manager.handle_actions(_frame(8, InputAction.CONFIRM))
    assert manager.current.settings.effects_reduced
    manager.handle_actions(_frame(9, InputAction.CANCEL))

    assert manager.current_name == "pause"
    assert session.round_state is RoundState.PAUSED
    assert persistence.load_settings() is not None
    assert persistence.load_settings().effects_reduced


@pytest.mark.parametrize("height", [480, 720, 1080])
def test_nine_choice_menu_rows_fit_between_subtitle_and_footer(height: int) -> None:
    layout = calculate_menu_layout(
        height,
        subtitle_lines=1,
        choice_count=9,
        footer_lines=2,
    )
    last_choice_center = layout.choices_y + 8 * layout.choice_spacing
    choice_top = layout.choices_y - layout.body_font_size / 2
    choice_bottom = last_choice_center + layout.body_font_size / 2
    subtitle_bottom = layout.subtitle_y + layout.subtitle_spacing
    footer_top = layout.footer_y - layout.footer_font_size / 2

    assert choice_top > subtitle_bottom
    assert choice_bottom < footer_top
    assert layout.choice_spacing >= layout.body_font_size * 0.75
