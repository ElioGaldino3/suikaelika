"""CLI policy and native-only counting in a real dummy SDL runtime."""

from types import SimpleNamespace

import pytest
from test_controller_lifecycle import FakePad, FakeRegistry, _app

import suika_elika.app as app_module
from suika_elika.config import AppConfig
from suika_elika.contracts import InputAction, RoundState, SceneTransition
from suika_elika.input.battle import BattleControls
from suika_elika.input.manager import InputBackend, InputSample


@pytest.mark.parametrize(
    "args,desktop,indexes,debug",
    [
        ([], False, None, False),
        (["--desktop"], True, None, False),
        (["--window"], False, None, False),
        (["--p1-index", "2", "--p2-index", "0"], False, (2, 0), False),
        (["--debug"], False, None, True),
        (["--desktop", "--debug"], True, None, True),
    ],
)
def test_cli_constructs_expected_config(monkeypatch, args, desktop, indexes, debug):
    configs = []

    class App:
        def __init__(self, config):
            configs.append(config)

        def run(self):
            return 0

    monkeypatch.setattr(app_module, "App", App)
    assert app_module.main(args) == 0
    assert configs[0].allow_keyboard_fallback is desktop
    assert configs[0].player_indexes == indexes
    assert configs[0].debug_colliders is debug
    assert configs[0].fullscreen is ("--window" not in args)


@pytest.mark.parametrize(
    "args",
    [
        ["--p1-index", "0"],
        ["--p1-index", "0", "--p2-index", "0"],
        ["--p1-index", "-1", "--p2-index", "1"],
        ["--unknown"],
    ],
)
def test_cli_rejects_invalid_player_selection(args):
    with pytest.raises(SystemExit) as error:
        app_module.main(args)
    assert error.value.code == 2


def runtime(tmp_path, monkeypatch, config, count=0):
    import pygame

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pads = {10 + index: FakePad(str(index)) for index in range(count)}
    for index, pad in enumerate(pads.values()):
        pad.device_index = index
    registry = FakeRegistry(pads, active=10)
    registry.active_instance_id = None
    registry.discover = lambda: tuple(pads)
    registry.close = lambda: None
    _, _, old_manager = _app(tmp_path, FakeRegistry({10: FakePad("fixture")}, active=10))
    monkeypatch.setattr(app_module, "JsonPersistence", lambda: old_manager.persistence)
    monkeypatch.setattr(app_module, "NativeInputRegistry", lambda _: registry)
    monkeypatch.setattr(pygame.key, "get_focused", lambda: True)
    app = app_module.App(config, pygame_module=pygame)
    return app, registry


@pytest.mark.parametrize(
    "desktop,count,expected",
    [
        (False, 0, None),
        (True, 0, InputBackend.KEYBOARD_EMULATED),
        (True, 1, InputBackend.NATIVE),
        (False, 2, InputBackend.NATIVE),
    ],
)
def test_runtime_counts_only_native_pads_and_keyboard_requires_opt_in(
    tmp_path,
    monkeypatch,
    desktop,
    count,
    expected,
):
    app, _ = runtime(
        tmp_path, monkeypatch, AppConfig(fullscreen=False, allow_keyboard_fallback=desktop), count
    )
    assert app.run(frame_limit=1) == 0
    assert (app._keyboard is not None) is desktop
    assert app._input.active_backend is expected
    assert app.scene_manager.battle_ready is (count >= 2)
    assert f"{count} controle(s)" in app.scene_manager.current.snapshot.subtitle


def test_selected_indexes_define_p1_and_p2_with_three_pads(tmp_path, monkeypatch):
    app, registry = runtime(
        tmp_path, monkeypatch, AppConfig(fullscreen=False, player_indexes=(2, 0)), 3
    )
    assert app.run(frame_limit=1) == 0
    assert registry.active_instance_id == 12
    assert app._battle_controls.slots == [12, 10]


@pytest.mark.parametrize("desktop", [False, True])
def test_real_key_event_is_ignored_without_desktop_and_enters_classic_with_it(
    tmp_path,
    monkeypatch,
    desktop,
):
    import pygame

    app, _ = runtime(
        tmp_path,
        monkeypatch,
        AppConfig(fullscreen=False, allow_keyboard_fallback=desktop),
    )
    batches = [[SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_RETURN)], []]
    monkeypatch.setattr(pygame.event, "get", lambda: batches.pop(0))
    assert app.run(frame_limit=2) == 0
    assert app.scene_manager.current_name == ("play" if desktop else "title")
    assert not app.scene_manager.battle_ready


def test_unavailable_selection_fails_visibly(tmp_path, monkeypatch, capsys):
    app, _ = runtime(tmp_path, monkeypatch, AppConfig(fullscreen=False, player_indexes=(2, 0)), 1)
    assert app.run(frame_limit=1) == 1
    assert "índices: [2]" in capsys.readouterr().err


def test_explicit_slots_survive_reconnect_and_return_to_menu():
    registry = FakeRegistry({10: FakePad("one"), 20: FakePad("two"), 30: FakePad("three")}, 30)
    controls = BattleControls(registry, preferred_instances=(30, 10))
    controls.sync(locked=False)
    assert controls.slots == [30, 10]
    registry.devices.pop(30)
    controls.sync(locked=True)
    assert controls.slots == [None, 10]
    registry.devices[99] = FakePad("three")
    controls.sync(locked=True)
    controls.sync(locked=False)
    assert controls.slots == [99, 10]


def test_desktop_can_confirm_keyboard_fallback_after_native_disconnect(tmp_path):
    registry = FakeRegistry({10: FakePad("one")}, 10)
    app, session, manager = _app(tmp_path, registry)
    keyboard = FakePad(
        "keyboard",
        InputSample(
            action_edges=(InputAction.CONFIRM, InputAction.DROP),
        ),
    )
    keyboard.clear = lambda: None
    keyboard.process_events = lambda events: None
    app._keyboard = keyboard
    app._input.register_adapter(InputBackend.KEYBOARD_EMULATED, keyboard)
    manager.transition(SceneTransition("play"))
    app._process_events((SimpleNamespace(type=1, kind="remove", instance_id=10),))
    assert session.round_state is RoundState.PAUSED
    assert app._input.active_backend is InputBackend.KEYBOARD_EMULATED
    app._poll_and_dispatch(0, ())
    assert not app._controller_reconnect_lock
    app._advance_simulation(0.02)
    assert session.drop_count == 0
