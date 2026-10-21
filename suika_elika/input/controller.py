"""Pygame SDL2 controller adapter and controller-preferred hotplug registry."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any

from suika_elika.contracts.input import InputAction

from .joystick import JoystickAdapter, JoystickBindings
from .manager import InputSample

_AUTO = object()


def normalize_controller_axis(value: int) -> float:
    """Normalize SDL2 Controller axes without dividing the negative extreme by 32767."""
    if type(value) is not int:
        raise TypeError("controller axis must be an integer")
    if not -32768 <= value <= 32767:
        raise ValueError("controller axis must be in [-32768, 32767]")
    return value / 32768.0 if value < 0 else value / 32767.0


class SDLControllerAdapter:
    """Read one SDL-mapped controller using standardized Controller constants."""

    def __init__(
        self,
        controller: Any,
        *,
        controller_api: Any,
        device_index: int,
        button_actions: Mapping[int, tuple[InputAction, ...]] | None = None,
    ) -> None:
        if type(device_index) is not int or device_index < 0:
            raise ValueError("device_index must be a non-negative integer")
        self.controller = controller
        self.controller_api = controller_api
        self.device_index = device_index
        joystick = controller.as_joystick()
        self.instance_id = int(joystick.get_instance_id())
        self.name = _read_metadata(joystick, "get_name", "Mapped controller")
        self.guid = _read_metadata(joystick, "get_guid", "")
        self._joystick = joystick
        self._button_actions = dict(button_actions or _default_controller_actions(controller_api))
        self._button_states: dict[int, bool] = {}
        self._closed = False

    @classmethod
    def open(
        cls,
        device_index: int,
        *,
        controller_api: Any | None = None,
        button_actions: Mapping[int, tuple[InputAction, ...]] | None = None,
    ) -> SDLControllerAdapter | None:
        """Open a mapped controller, returning None when the API/device is unavailable."""
        api = controller_api if controller_api is not None else _load_controller_api()
        if api is None:
            return None
        try:
            if not api.is_controller(device_index):
                return None
            controller = api.Controller(device_index)
            return cls(
                controller,
                controller_api=api,
                device_index=device_index,
                button_actions=button_actions,
            )
        except Exception:
            return None

    def poll(self) -> InputSample:
        """Poll controller axes/buttons into the shared normalized contract."""
        if self._closed:
            return InputSample()
        api = self.controller_api
        axis_x = normalize_controller_axis(
            int(self.controller.get_axis(_constant(api, "CONTROLLER_AXIS_LEFTX", 0)))
        )
        axis_y = normalize_controller_axis(
            int(self.controller.get_axis(_constant(api, "CONTROLLER_AXIS_LEFTY", 1)))
        )
        left = self._pressed_constant("CONTROLLER_BUTTON_DPAD_LEFT")
        right = self._pressed_constant("CONTROLLER_BUTTON_DPAD_RIGHT")
        up = self._pressed_constant("CONTROLLER_BUTTON_DPAD_UP")
        down = self._pressed_constant("CONTROLLER_BUTTON_DPAD_DOWN")
        fine_adjust = self._pressed_constant("CONTROLLER_BUTTON_LEFTSHOULDER")

        edges: list[InputAction] = []
        drop_held = False
        for button, actions in self._button_actions.items():
            is_down = bool(self.controller.get_button(button))
            was_down = self._button_states.get(button, False)
            if is_down and not was_down:
                edges.extend(actions)
            self._button_states[button] = is_down
            if is_down and InputAction.DROP in actions:
                drop_held = True

        return InputSample(
            analog_x=axis_x,
            analog_y=axis_y,
            left=left,
            right=right,
            up=up,
            down=down,
            fine_adjust=fine_adjust,
            action_edges=tuple(edges),
            drop_held=drop_held,
        )

    def reset_edges(self) -> None:
        """Synchronize held state after remap so held buttons cannot retrigger."""
        self._button_states = {
            button: bool(self.controller.get_button(button))
            for button in self._button_actions
        }

    def rumble(self, low_frequency: float, high_frequency: float, duration_ms: int) -> bool:
        """Use controller rumble when available, then its underlying joystick API."""
        rumble = getattr(self.controller, "rumble", None)
        if not callable(rumble):
            rumble = getattr(self._joystick, "rumble", None)
        if not callable(rumble):
            return False
        try:
            return bool(rumble(low_frequency, high_frequency, duration_ms))
        except Exception:
            return False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        quit_controller = getattr(self.controller, "quit", None)
        if callable(quit_controller):
            quit_controller()

    def _pressed_constant(self, name: str) -> bool:
        value = getattr(self.controller_api, name, None)
        return value is not None and bool(self.controller.get_button(value))


class NativeInputRegistry:
    """Track native devices by instance ID, preferring SDL Controller when mapped.

    Feed the Pygame event batch to ``process_events`` once per frame. If SDL emits
    both Controller and Joystick add events for a device, the registry opens that
    ``device_index`` once and selects the Controller path. Consequently the same
    physical device never contributes a second action stream through Joystick.
    """

    def __init__(
        self,
        pygame_module: Any | None = None,
        *,
        controller_api: Any = _AUTO,
        joystick_bindings: JoystickBindings | None = None,
    ) -> None:
        if pygame_module is None:
            pygame_module = importlib.import_module("pygame")
        self.pygame = pygame_module
        self.controller_api = (
            _load_controller_api() if controller_api is _AUTO else controller_api
        )
        self.joystick_bindings = joystick_bindings
        self._devices: dict[int, SDLControllerAdapter | JoystickAdapter] = {}
        self._device_index_to_instance: dict[int, int] = {}
        self.active_instance_id: int | None = None

    @property
    def devices(self) -> Mapping[int, SDLControllerAdapter | JoystickAdapter]:
        """A read-only copy keyed by connection-scoped instance ID."""
        return MappingProxyType(dict(self._devices))

    def discover(self) -> tuple[int, ...]:
        """Open devices currently enumerated by Pygame, once per device index."""
        module = self.pygame.joystick
        initializer = getattr(module, "init", None)
        if callable(initializer):
            initializer()
        controller_init = getattr(self.controller_api, "init", None)
        if callable(controller_init):
            try:
                controller_init()
            except Exception:
                # Generic joystick support remains available if Controller init fails.
                self.controller_api = None

        added: list[int] = []
        for device_index in range(int(module.get_count())):
            instance_id = self._open_index(device_index)
            if instance_id is not None:
                added.append(instance_id)
        return tuple(added)

    def process_events(self, events: Iterable[Any]) -> tuple[int, ...]:
        """Process hotplug/remap events and return newly connected instance IDs."""
        events = tuple(events)
        removed: set[int] = set()
        remapped: set[int] = set()
        added_indexes: set[int] = set()
        controller_add = _event_type(self.pygame, "CONTROLLERDEVICEADDED")
        joystick_add = _event_type(self.pygame, "JOYDEVICEADDED")
        controller_remove = _event_type(self.pygame, "CONTROLLERDEVICEREMOVED")
        joystick_remove = _event_type(self.pygame, "JOYDEVICEREMOVED")
        controller_remap = _event_type(self.pygame, "CONTROLLERDEVICEREMAPPED")

        for event in events:
            event_type = getattr(event, "type", None)
            if event_type in (controller_remove, joystick_remove):
                instance_id = int(event.instance_id)
                removed.add(instance_id)
            elif event_type == controller_remap:
                remapped.add(int(event.instance_id))
            elif event_type in (controller_add, joystick_add):
                added_indexes.add(int(event.device_index))

        for instance_id in removed:
            self._remove_instance(instance_id)
        if removed:
            # Device indices can shift after a disconnect; discard stale indexes.
            self._device_index_to_instance.clear()
        for instance_id in remapped:
            adapter = self._devices.get(instance_id)
            if isinstance(adapter, SDLControllerAdapter):
                adapter.reset_edges()

        added: list[int] = []
        for device_index in sorted(added_indexes):
            opened_instance_id = self._open_index(device_index)
            if opened_instance_id is not None:
                added.append(opened_instance_id)
        return tuple(added)

    def select(self, instance_id: int | None) -> None:
        """Select one connected native device as the only active input source."""
        if instance_id is not None and instance_id not in self._devices:
            raise ValueError(f"unknown input device instance {instance_id}")
        self.active_instance_id = instance_id

    def poll(self) -> InputSample:
        """Poll only the selected device; no selected device yields neutral input."""
        if self.active_instance_id is None:
            return InputSample()
        device = self._devices.get(self.active_instance_id)
        return device.poll() if device is not None else InputSample()

    def close(self) -> None:
        for instance_id in tuple(self._devices):
            self._remove_instance(instance_id)
        self.active_instance_id = None
        self._device_index_to_instance.clear()

    def _open_index(self, device_index: int) -> int | None:
        if type(device_index) is not int or device_index < 0:
            return None
        cached = self._device_index_to_instance.get(device_index)
        if cached in self._devices:
            return cached

        controller_adapter = (
            SDLControllerAdapter.open(device_index, controller_api=self.controller_api)
            if self.controller_api is not None
            else None
        )
        adapter: SDLControllerAdapter | JoystickAdapter
        if controller_adapter is not None:
            adapter = controller_adapter
        else:
            try:
                joystick = self.pygame.joystick.Joystick(device_index)
                adapter = JoystickAdapter(
                    joystick,
                    device_index=device_index,
                    bindings=self.joystick_bindings,
                )
            except Exception:
                return None

        instance_id = adapter.instance_id
        existing = self._devices.get(instance_id)
        if existing is not None:
            # The same connection can be reported by both Pygame event families.
            adapter.close()
            self._device_index_to_instance[device_index] = instance_id
            return instance_id
        self._devices[instance_id] = adapter
        self._device_index_to_instance[device_index] = instance_id
        return instance_id

    def _remove_instance(self, instance_id: int) -> None:
        adapter = self._devices.pop(instance_id, None)
        if adapter is not None:
            adapter.close()
        for device_index, mapped_id in tuple(self._device_index_to_instance.items()):
            if mapped_id == instance_id:
                del self._device_index_to_instance[device_index]
        if self.active_instance_id == instance_id:
            self.active_instance_id = None


def _load_controller_api() -> Any | None:
    """Import the optional SDL2 Controller extension without making it mandatory."""
    try:
        return importlib.import_module("pygame._sdl2.controller")
    except (ImportError, ModuleNotFoundError):
        return None


def _default_controller_actions(api: Any) -> dict[int, tuple[InputAction, ...]]:
    actions: dict[int, tuple[InputAction, ...]] = {}
    button_a = getattr(api, "CONTROLLER_BUTTON_A", None)
    button_b = getattr(api, "CONTROLLER_BUTTON_B", None)
    button_start = getattr(api, "CONTROLLER_BUTTON_START", None)
    if button_a is not None:
        # The south face button confirms menus and releases fruit in gameplay;
        # scenes consume only the action relevant to their current state.
        actions[int(button_a)] = (InputAction.CONFIRM, InputAction.DROP)
    if button_b is not None:
        actions[int(button_b)] = (InputAction.CANCEL,)
    if button_start is not None:
        actions[int(button_start)] = (InputAction.PAUSE,)
    return actions


def _constant(api: Any, name: str, fallback: int) -> int:
    value = getattr(api, name, fallback)
    return int(value)


def _event_type(pygame_module: Any, name: str) -> Any:
    return getattr(pygame_module, name, object())


def _read_metadata(device: Any, getter: str, fallback: str) -> str:
    method = getattr(device, getter, None)
    if not callable(method):
        return fallback
    try:
        return str(method())
    except Exception:
        return fallback
