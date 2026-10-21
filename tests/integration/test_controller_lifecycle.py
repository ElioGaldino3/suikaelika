"""End-to-end checks for exclusive native controller ownership and recovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from suika_elika.app import App
from suika_elika.audio import NullAudioManager
from suika_elika.config import AppConfig
from suika_elika.contracts import InputAction, RoundState, SceneTransition
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.input.manager import InputBackend, InputManager, InputSample
from suika_elika.persistence import JsonPersistence
from suika_elika.platform import resolve_user_paths
from suika_elika.scene_manager import SceneManager


class FakePad:
    def __init__(self, guid: str, *samples: InputSample) -> None:
        self.guid = guid
        self.name = f"Pad {guid}"
        self.samples = list(samples)
        self.poll_count = 0

    def poll(self) -> InputSample:
        self.poll_count += 1
        return self.samples.pop(0) if self.samples else InputSample()

    def reset_edges(self) -> None:
        pass


class FakeRegistry:
    """Small hotplug registry fake that retains the selected device only."""

    def __init__(self, devices: dict[int, FakePad], active: int) -> None:
        self.devices = devices
        self.active_instance_id: int | None = active

    def process_events(self, events: tuple[object, ...]) -> tuple[int, ...]:
        added: list[int] = []
        for event in events:
            if getattr(event, "kind", None) == "remove":
                instance_id = int(event.instance_id)
                self.devices.pop(instance_id, None)
                if self.active_instance_id == instance_id:
                    self.active_instance_id = None
            elif getattr(event, "kind", None) == "add":
                instance_id = int(event.instance_id)
                self.devices[instance_id] = event.device
                added.append(instance_id)
        return tuple(added)

    def select(self, instance_id: int | None) -> None:
        if instance_id is not None and instance_id not in self.devices:
            raise ValueError("unknown fake controller")
        self.active_instance_id = instance_id

    def poll(self) -> InputSample:
        if self.active_instance_id is None:
            return InputSample()
        return self.devices[self.active_instance_id].poll()


def _app(tmp_path: Path, registry: FakeRegistry) -> tuple[App, GameSession, SceneManager]:
    persistence = JsonPersistence(
        resolve_user_paths(
            config_dir=tmp_path / "config",
            data_dir=tmp_path / "data",
            log_dir=tmp_path / "logs",
            system="Linux",
            batocera=False,
        )
    )
    session = GameSession(PhysicsWorld(), persistence=persistence, seed=8)
    input_manager = InputManager()
    input_manager.register_adapter(InputBackend.NATIVE, registry)
    input_manager.select_backend(InputBackend.NATIVE)
    scene_manager = SceneManager(
        session, persistence, input_manager, NullAudioManager()
    )
    app = App(AppConfig(fullscreen=False))
    app._registry = registry  # type: ignore[assignment]
    app._pygame = SimpleNamespace(WINDOWFOCUSLOST=-100, WINDOWFOCUSGAINED=-101)
    app._input = input_manager
    app._manager = scene_manager
    app._session = session
    app._audio = scene_manager.audio
    selected = registry.devices[registry.active_instance_id]  # type: ignore[index]
    app._selected_controller_identity = app._controller_identity(selected)
    return app, session, scene_manager


def test_removed_controller_pauses_and_reconnect_confirmation_cannot_drop(
    tmp_path: Path,
) -> None:
    pad = FakePad("player-one")
    registry = FakeRegistry({10: pad}, active=10)
    app, session, manager = _app(tmp_path, registry)
    manager.transition(SceneTransition("play"))

    app._process_events((SimpleNamespace(type=1, kind="remove", instance_id=10),))

    assert session.round_state is RoundState.PAUSED
    assert app._controller_reconnect_lock
    assert app._input.active_backend is None
    assert manager.current_name == "play"

    replacement = FakePad(
        "player-one",
        InputSample(action_edges=(InputAction.CONFIRM, InputAction.DROP)),
    )
    app._process_events(
        (SimpleNamespace(type=1, kind="add", instance_id=21, device=replacement),)
    )
    assert registry.active_instance_id == 21
    assert app._input.active_backend is InputBackend.NATIVE

    app._poll_and_dispatch(0.0, ())

    assert not app._controller_reconnect_lock
    assert session.round_state is RoundState.READY
    assert session.drop_count == 0
    assert manager.current_name == "play"


def test_second_controller_is_not_selected_or_polled_automatically(
    tmp_path: Path,
) -> None:
    first = FakePad("player-one", InputSample(action_edges=(InputAction.DROP,)))
    second = FakePad("player-two", InputSample(action_edges=(InputAction.DROP,)))
    registry = FakeRegistry({10: first}, active=10)
    app, _session, _manager = _app(tmp_path, registry)

    app._process_events(
        (SimpleNamespace(type=1, kind="add", instance_id=22, device=second),)
    )
    sample = registry.poll()

    assert registry.active_instance_id == 10
    assert sample.action_edges == (InputAction.DROP,)
    assert first.poll_count == 1
    assert second.poll_count == 0

    app._process_events((SimpleNamespace(type=1, kind="remove", instance_id=10),))

    assert registry.active_instance_id is None
    assert app._input.active_backend is None
    assert app._controller_reconnect_lock
    assert registry.poll().action_edges == ()
    assert second.poll_count == 0


def test_input_manager_reads_only_the_selected_backend() -> None:
    class Adapter:
        def __init__(self, action: InputAction) -> None:
            self.action = action

        def poll(self) -> InputSample:
            return InputSample(action_edges=(self.action,))

    manager = InputManager()
    manager.register_adapter(InputBackend.NATIVE, Adapter(InputAction.DROP))
    manager.register_adapter(InputBackend.KEYBOARD_EMULATED, Adapter(InputAction.CONFIRM))

    manager.select_backend(InputBackend.NATIVE)
    native = manager.poll(0.0).frame
    manager.select_backend(InputBackend.KEYBOARD_EMULATED)
    keyboard = manager.poll(0.0).frame

    assert [edge.action for edge in native.edges] == [InputAction.DROP]
    assert [edge.action for edge in keyboard.edges] == [InputAction.CONFIRM]
    assert native.edges[0].sequence < keyboard.edges[0].sequence
