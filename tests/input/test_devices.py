"""Simulated Pygame device checks; no physical joystick is opened by this suite."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from suika_elika.contracts.input import InputAction
from suika_elika.input.battle import BattleControls
from suika_elika.input.controller import (
    NativeInputRegistry,
    SDLControllerAdapter,
    normalize_controller_axis,
)
from suika_elika.input.joystick import JoystickAdapter, JoystickBindings


class FakeJoystick:
    def __init__(
        self,
        instance_id: int,
        *,
        axes: tuple[float, ...] = (0.0, 0.0),
        buttons: tuple[bool, ...] = (),
        hats: tuple[tuple[int, int], ...] = ((0, 0),),
        rumble_result: bool | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.axes = axes
        self.buttons = buttons
        self.hats = hats
        self.rumble_result = rumble_result
        self.quit_calls = 0

    def get_instance_id(self) -> int:
        return self.instance_id

    def get_name(self) -> str:
        return "Simulated pad"

    def get_guid(self) -> str:
        return "sim-guid"

    def get_numaxes(self) -> int:
        return len(self.axes)

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def get_numbuttons(self) -> int:
        return len(self.buttons)

    def get_button(self, index: int) -> bool:
        return self.buttons[index]

    def get_numhats(self) -> int:
        return len(self.hats)

    def get_hat(self, index: int) -> tuple[int, int]:
        return self.hats[index]

    def rumble(self, low: float, high: float, duration: int) -> bool:
        return bool(self.rumble_result)

    def quit(self) -> None:
        self.quit_calls += 1


class FakeController:
    def __init__(self, joystick: FakeJoystick) -> None:
        self.joystick = joystick
        self.axes: dict[int, int] = {0: 0, 1: 0}
        self.buttons: dict[int, bool] = {}
        self.quit_calls = 0

    def as_joystick(self) -> FakeJoystick:
        return self.joystick

    def get_axis(self, index: int) -> int:
        return self.axes.get(index, 0)

    def get_button(self, index: int) -> bool:
        return self.buttons.get(index, False)

    def quit(self) -> None:
        self.quit_calls += 1


class FakeControllerApi:
    CONTROLLER_AXIS_LEFTX = 0
    CONTROLLER_AXIS_LEFTY = 1
    CONTROLLER_BUTTON_A = 0
    CONTROLLER_BUTTON_B = 1
    CONTROLLER_BUTTON_START = 2
    CONTROLLER_BUTTON_DPAD_UP = 3
    CONTROLLER_BUTTON_DPAD_DOWN = 4
    CONTROLLER_BUTTON_DPAD_LEFT = 5
    CONTROLLER_BUTTON_DPAD_RIGHT = 6
    CONTROLLER_BUTTON_LEFTSHOULDER = 7

    def __init__(self) -> None:
        self.controllers: list[FakeController] = []
        self.opened_indexes: list[int] = []

    def init(self) -> None:
        pass

    def is_controller(self, device_index: int) -> bool:
        return device_index == 0

    def Controller(self, device_index: int) -> FakeController:
        self.opened_indexes.append(device_index)
        joystick = FakeJoystick(700 + device_index)
        controller = FakeController(joystick)
        self.controllers.append(controller)
        return controller


class FakeJoystickModule:
    def __init__(self, devices: tuple[FakeJoystick, ...]) -> None:
        self.devices = devices
        self.init_calls = 0
        self.opened_indexes: list[int] = []

    def init(self) -> None:
        self.init_calls += 1

    def get_count(self) -> int:
        return len(self.devices)

    def Joystick(self, device_index: int) -> FakeJoystick:
        self.opened_indexes.append(device_index)
        return self.devices[device_index]


def _pygame(joysticks: FakeJoystickModule) -> SimpleNamespace:
    return SimpleNamespace(
        joystick=joysticks,
        CONTROLLERDEVICEADDED=100,
        JOYDEVICEADDED=101,
        CONTROLLERDEVICEREMOVED=102,
        JOYDEVICEREMOVED=103,
        CONTROLLERDEVICEREMAPPED=104,
    )


def test_controller_axis_normalization_uses_signed_sdl_integer_range() -> None:
    assert normalize_controller_axis(-32768) == -1.0
    assert normalize_controller_axis(0) == 0.0
    assert normalize_controller_axis(32767) == 1.0
    assert normalize_controller_axis(-16384) == pytest.approx(-0.5)
    with pytest.raises(ValueError, match="-32768, 32767"):
        normalize_controller_axis(32768)
    with pytest.raises(TypeError, match="integer"):
        normalize_controller_axis(0.5)  # type: ignore[arg-type]


def test_controller_uses_device_index_to_open_and_instance_id_for_runtime() -> None:
    api = FakeControllerApi()
    joystick_module = FakeJoystickModule((FakeJoystick(99),))
    registry = NativeInputRegistry(_pygame(joystick_module), controller_api=api)

    connected = registry.process_events(
        (
            SimpleNamespace(type=100, device_index=0),
            SimpleNamespace(type=101, device_index=0),
        )
    )

    assert connected == (700,)
    assert api.opened_indexes == [0]  # not instance ID 700
    assert joystick_module.opened_indexes == []  # no duplicate Joystick path
    assert tuple(registry.devices) == (700,)
    assert isinstance(registry.devices[700], SDLControllerAdapter)

    controller = api.controllers[0]
    controller.axes.update({0: -32768, 1: 16384})
    controller.buttons[api.CONTROLLER_BUTTON_A] = True
    registry.select(700)
    sample = registry.poll()
    assert sample.analog_x == -1.0
    assert sample.analog_y == pytest.approx(0.5, abs=2e-5)
    assert sample.action_edges == (InputAction.CONFIRM, InputAction.DROP)
    assert sample.drop_held
    assert registry.poll().drop_held
    assert registry.poll().action_edges == ()


def test_controller_remap_resets_button_edges_and_remove_clears_selection() -> None:
    api = FakeControllerApi()
    module = FakeJoystickModule((FakeJoystick(9),))
    registry = NativeInputRegistry(_pygame(module), controller_api=api)
    registry.process_events((SimpleNamespace(type=100, device_index=0),))
    controller = api.controllers[0]
    controller.buttons[api.CONTROLLER_BUTTON_A] = True
    registry.select(700)

    assert registry.poll().action_edges == (InputAction.CONFIRM, InputAction.DROP)
    assert registry.process_events((SimpleNamespace(type=104, instance_id=700),)) == ()
    assert registry.poll().action_edges == ()  # still-held A does not become a second edge

    controller.buttons[api.CONTROLLER_BUTTON_A] = False
    assert registry.poll().action_edges == ()
    controller.buttons[api.CONTROLLER_BUTTON_A] = True
    assert registry.poll().action_edges == (InputAction.CONFIRM, InputAction.DROP)

    registry.process_events((SimpleNamespace(type=102, instance_id=700),))
    assert registry.devices == {}
    assert registry.active_instance_id is None
    assert registry.poll().action_edges == ()
    assert controller.quit_calls == 1


def test_generic_joystick_uses_float_axes_hat_and_no_guessed_button_mapping() -> None:
    joystick = FakeJoystick(
        55,
        axes=(0.65, -0.4),
        buttons=(True,),
        hats=((-1, 1),),
    )
    adapter = JoystickAdapter(joystick, device_index=2)

    sample = adapter.poll()
    assert sample.analog_x == 0.65
    assert sample.analog_y == -0.4
    assert sample.left and sample.up
    assert sample.action_edges == ()  # button 0 has no universal meaning
    assert adapter.rumble(0.3, 0.8, 250) is False


def test_generic_button_mapping_emits_one_edge_and_rumble_is_optional() -> None:
    joystick = FakeJoystick(56, buttons=(True,), rumble_result=True)
    adapter = JoystickAdapter(
        joystick,
        device_index=0,
        bindings=JoystickBindings(button_actions={0: (InputAction.DROP,)}),
    )

    assert adapter.poll().action_edges == (InputAction.DROP,)
    assert adapter.poll().action_edges == ()
    assert adapter.poll().drop_held
    adapter.reset_edges()
    assert adapter.poll().action_edges == ()
    joystick.buttons = (False,)
    assert not adapter.poll().drop_held
    assert adapter.rumble(0.2, 0.7, 150)


def test_controller_import_absence_falls_back_without_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_: str) -> Any:
        raise ImportError("simulated build without pygame._sdl2.controller")

    monkeypatch.setattr("suika_elika.input.controller.importlib.import_module", unavailable)
    assert SDLControllerAdapter.open(0) is None

    module = FakeJoystickModule((FakeJoystick(60),))
    registry = NativeInputRegistry(_pygame(module), controller_api=None)
    assert registry.process_events((SimpleNamespace(type=101, device_index=0),)) == (60,)
    assert isinstance(registry.devices[60], JoystickAdapter)


def test_generic_device_removal_uses_instance_id_not_current_index() -> None:
    joystick = FakeJoystick(900)
    module = FakeJoystickModule((joystick,))
    registry = NativeInputRegistry(_pygame(module), controller_api=None)
    registry.discover()
    registry.select(900)

    # Device removal events carry an instance_id, not the open-time device_index.
    registry.process_events((SimpleNamespace(type=103, instance_id=900),))
    assert registry.devices == {}
    assert joystick.quit_calls == 1
    assert registry.active_instance_id is None


@pytest.mark.parametrize("both_mapped", [False, True])
def test_two_native_pads_are_distinct_despite_duplicate_sdl_add_events(both_mapped) -> None:
    api = FakeControllerApi()
    if both_mapped:
        api.is_controller = lambda index: True
    generic = FakeJoystick(900, buttons=(False,))
    module = FakeJoystickModule((FakeJoystick(99), generic))
    registry = NativeInputRegistry(
        _pygame(module), controller_api=api,
        joystick_bindings=JoystickBindings(button_actions={0: (InputAction.DROP,)}),
    )
    registry.process_events(tuple(
        SimpleNamespace(type=event_type, device_index=index)
        for index in (0, 1) for event_type in (100, 101)
    ))
    assert len(registry.devices) == 2
    controls = BattleControls(registry)
    controls.sync(locked=False)
    api.controllers[0].buttons[api.CONTROLLER_BUTTON_A] = True
    api.controllers[0].axes[0] = -32768
    if both_mapped:
        api.controllers[1].buttons[api.CONTROLLER_BUTTON_A] = True
        api.controllers[1].axes[0] = 32767
    else:
        generic.buttons = (True,)
        generic.axes = (1.0, 0.0)
    first, second = controls.poll(0)
    assert first.move_x == -1 and second.move_x == 1
    assert any(edge.action is InputAction.DROP for edge in first.edges)
    assert any(edge.action is InputAction.DROP for edge in second.edges)
    assert controls.poll(0)[0].edges == controls.poll(0)[1].edges == ()
    registry.close()


def test_controller_api_without_constants_uses_real_pygame_namespace() -> None:
    import pygame
    from pygame._sdl2 import controller as controller_api

    device = FakeController(FakeJoystick(42))
    adapter = SDLControllerAdapter(device, controller_api=controller_api, device_index=0)
    device.buttons.update({
        pygame.CONTROLLER_BUTTON_A: True,
        pygame.CONTROLLER_BUTTON_DPAD_DOWN: True,
        pygame.CONTROLLER_BUTTON_LEFTSHOULDER: True,
    })
    sample = adapter.poll()
    assert sample.action_edges == (InputAction.CONFIRM, InputAction.DROP)
    assert sample.down and sample.fine_adjust and sample.drop_held
    assert adapter.poll().action_edges == ()
    device.buttons.clear()
    adapter.poll()
    device.buttons[pygame.CONTROLLER_BUTTON_B] = True
    device.buttons[pygame.CONTROLLER_BUTTON_START] = True
    assert adapter.poll().action_edges == (InputAction.CANCEL, InputAction.PAUSE)
