"""Simultaneous joystick routing, menus, and battle recovery without hardware."""

from types import SimpleNamespace

import pytest
from test_controller_lifecycle import FakePad, FakeRegistry, _app

from suika_elika.contracts import InputAction, InputEdge, InputFrame, RoundState, SceneTransition
from suika_elika.input.battle import BattleControls
from suika_elika.input.manager import InputSample
from suika_elika.scenes.title import TitleScene


def frame(sequence: int, action: InputAction) -> InputFrame:
    return InputFrame(edges=(InputEdge(sequence, action),))


def setup_battle(tmp_path, *, identical=False):
    first, second = FakePad("same" if identical else "one"), FakePad("same" if identical else "two")
    registry = FakeRegistry({10: first, 20: second}, active=10)
    app, _, manager = _app(tmp_path, registry)
    app._battle_controls = BattleControls(registry)
    app._battle_controls.sync(locked=False)
    manager.set_controller_count(2)
    manager.transition(SceneTransition("battle"))
    return app, registry, manager, first, second


def test_title_battle_gate_updates_with_hotplug(tmp_path) -> None:
    registry = FakeRegistry({10: FakePad("one")}, active=10)
    app, _, manager = _app(tmp_path, registry)
    manager.set_controller_count(1)
    manager.handle_actions(frame(0, InputAction.NAV_DOWN))
    assert isinstance(manager.current, TitleScene)
    assert manager.current.snapshot.choices[1] == "BATALHA"
    assert 1 in manager.current.snapshot.disabled_indices
    manager.handle_actions(frame(1, InputAction.CONFIRM))
    assert manager.current_name == "title"
    app._process_events(
        (SimpleNamespace(type=1, kind="add", instance_id=20, device=FakePad("two")),)
    )
    assert not manager.current.snapshot.disabled_indices
    manager.handle_actions(frame(2, InputAction.CONFIRM))
    assert manager.current_name == "battle_setup"
    manager.handle_actions(frame(3, InputAction.CONFIRM))
    assert manager.current_name == "battle"


def test_two_pads_polled_once_and_drop_edges_do_not_repeat_in_substeps(tmp_path) -> None:
    app, _, manager, first, second = setup_battle(tmp_path)
    first.samples.append(InputSample(left=True, action_edges=(InputAction.DROP,)))
    second.samples.append(InputSample(right=True, action_edges=(InputAction.DROP,)))
    app._poll_and_dispatch(0.02, ())
    app._advance_simulation(0.02)
    assert first.poll_count == second.poll_count == 1
    one, two = manager.battle_session.players
    assert one.drop_count == two.drop_count == 1
    assert one.snapshot.launcher_x < two.snapshot.launcher_x


@pytest.mark.parametrize("removed_id", [10, 20])
@pytest.mark.parametrize("identical", [False, True])
def test_disconnect_reconnect_keeps_survivor_slot_and_consumes_confirm(
    tmp_path,
    removed_id,
    identical,
) -> None:
    app, registry, manager, _, _ = setup_battle(tmp_path, identical=identical)
    removed = registry.devices[removed_id]
    app._process_events((SimpleNamespace(type=1, kind="remove", instance_id=removed_id),))
    assert app._battle_connection_lock
    assert all(p.round_state is RoundState.PAUSED for p in manager.battle_session.players)
    survivor_slot = 1 if removed_id == 10 else 0
    survivor_id = 20 if removed_id == 10 else 10
    assert app._battle_controls.slots[survivor_slot] == survivor_id
    assert app._advance_simulation(0.1) == 0
    replacement = FakePad(
        removed.guid,
        InputSample(
            action_edges=(InputAction.CONFIRM, InputAction.DROP),
        ),
    )
    app._process_events((SimpleNamespace(type=1, kind="add", instance_id=99, device=replacement),))
    app._poll_and_dispatch(0.02, ())
    assert not app._battle_connection_lock
    app._advance_simulation(0.02)
    assert all(p.drop_count == 0 for p in manager.battle_session.players)
    assert app._battle_controls.slots[survivor_slot] == survivor_id
    assert 99 in app._battle_controls.slots


def test_second_player_can_pause_resume_and_navigate_results(tmp_path) -> None:
    app, _, manager, _, second = setup_battle(tmp_path)
    second.samples.append(InputSample(action_edges=(InputAction.PAUSE,)))
    app._poll_and_dispatch(0, ())
    assert manager.current_name == "pause"
    second.samples.append(InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)))
    app._poll_and_dispatch(0, ())
    assert manager.current_name == "battle"
    app._advance_simulation(0.02)
    assert all(p.drop_count == 0 for p in manager.battle_session.players)
    manager.battle_session.players[1]._score = 1000
    app._advance_simulation(0.02)
    manager.update(0)
    assert manager.current_name == "battle_results"
    assert "Jogador 2 venceu" in manager.current.snapshot.title
    second.samples.append(InputSample(action_edges=(InputAction.CONFIRM,)))
    app._poll_and_dispatch(0, ())
    assert manager.current_name == "battle"
    assert not manager.battle_session.finished


def test_focus_confirmation_from_second_player_does_not_drop(tmp_path) -> None:
    app, _, manager, _, second = setup_battle(tmp_path)
    app._lose_focus()
    assert all(p.round_state is RoundState.PAUSED for p in manager.battle_session.players)
    app._focused = True
    second.samples.append(InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)))
    app._poll_focus_confirmation(0, ())
    assert not app._focus_lock
    app._advance_simulation(0.02)
    assert all(p.drop_count == 0 for p in manager.battle_session.players)


def test_survivor_can_leave_disconnected_battle(tmp_path) -> None:
    app, _, manager, _, second = setup_battle(tmp_path)
    app._process_events((SimpleNamespace(type=1, kind="remove", instance_id=10),))
    second.samples.append(InputSample(action_edges=(InputAction.CANCEL,)))
    app._poll_and_dispatch(0, ())
    assert manager.current_name == "title" and not manager.battle_mode
    assert not app._battle_connection_lock


def test_real_app_loop_enters_renders_and_pauses_battle_with_simulated_pads(
    tmp_path,
    monkeypatch,
) -> None:
    import pygame

    import suika_elika.app as app_module
    from suika_elika.config import AppConfig

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    first, second = FakePad("one"), FakePad("two")
    registry = FakeRegistry({10: first, 20: second}, active=10)
    registry.discover = lambda: (10, 20)
    registry.close = lambda: None
    _, _, old_manager = _app(tmp_path, registry)
    monkeypatch.setattr(app_module, "JsonPersistence", lambda: old_manager.persistence)
    monkeypatch.setattr(app_module, "NativeInputRegistry", lambda _: registry)
    monkeypatch.setattr(pygame.key, "get_focused", lambda: True)
    event_get = pygame.event.get
    counter = 0

    def events():
        nonlocal counter
        batch = event_get()
        if counter == 0:
            first.samples.append(InputSample(down=True))
        elif counter == 2:
            first.samples.append(InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)))
        elif counter == 3:
            first.samples.append(InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)))
        elif counter == 4:
            first.samples.append(InputSample(action_edges=(InputAction.DROP,)))
            second.samples.append(InputSample(action_edges=(InputAction.DROP,)))
        elif counter == 6:
            second.samples.append(InputSample(action_edges=(InputAction.PAUSE,)))
        elif counter == 7:
            second.samples.append(InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)))
        counter += 1
        return batch

    monkeypatch.setattr(pygame.event, "get", events)
    app = app_module.App(AppConfig(fullscreen=False), pygame_module=pygame)
    assert app.run(frame_limit=10) == 0
    assert app.scene_manager.current_name == "battle"
    assert all(p.drop_count == 1 for p in app.scene_manager.battle_session.players)
    assert app._battle_renderer.presentation_rect[2] > 0


@pytest.mark.parametrize(("index", "target"), [(0, 1000), (1, 2000), (2, 5000)])
def test_choose_goal_win_and_rematch_preserve_target(tmp_path, index, target):
    registry = FakeRegistry({10: FakePad("one"), 20: FakePad("two")}, active=10)
    _, _, manager = _app(tmp_path, registry)
    manager.set_controller_count(2)
    manager.handle_actions(frame(0, InputAction.NAV_DOWN))
    manager.handle_actions(frame(1, InputAction.CONFIRM))
    assert manager.current_name == "battle_setup"
    assert manager.current.snapshot.choices == ("1000 pontos", "2000 pontos", "5000 pontos")
    assert not manager.battle_mode
    for step in range(index):
        manager.handle_actions(frame(2 + step, InputAction.NAV_DOWN))
    manager.handle_actions(frame(5, InputAction.CONFIRM))
    assert manager.current_name == "battle"
    assert manager.battle_session.snapshot.target == target
    assert all(p.drop_count == 0 for p in manager.battle_session.players)
    manager.battle_session.players[0]._score = target - 1
    manager.simulation_step()
    assert not manager.battle_session.finished
    manager.battle_session.players[0]._score = target
    manager.simulation_step()
    manager.update(0)
    assert manager.current_name == "battle_results"
    assert f"Meta de {target} pontos" in manager.current.snapshot.subtitle
    manager.handle_actions(frame(6, InputAction.CONFIRM))
    assert manager.current_name == "battle"
    assert manager.battle_session.target == target
    assert all(p.score == 0 for p in manager.battle_session.players)
    manager.transition(SceneTransition("pause"))
    manager.transition(SceneTransition("battle", (("resume", True),)))
    assert manager.battle_session.target == target


def test_goal_selection_cancel_and_hotplug_gate(tmp_path):
    registry = FakeRegistry({10: FakePad("one"), 20: FakePad("two")}, active=10)
    _, _, manager = _app(tmp_path, registry)
    manager.set_controller_count(2)
    manager.transition(SceneTransition("battle_setup"))
    manager.set_controller_count(1)
    assert manager.current.snapshot.disabled_indices == (0, 1, 2)
    manager.handle_actions(frame(0, InputAction.CONFIRM))
    assert manager.current_name == "battle_setup"
    manager.set_controller_count(2)
    assert not manager.current.snapshot.disabled_indices
    manager.handle_actions(frame(1, InputAction.CANCEL))
    assert manager.current_name == "title" and not manager.battle_mode
