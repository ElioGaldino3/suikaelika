"""Stable player slots over connection-scoped Pygame instance IDs."""

from __future__ import annotations

from suika_elika.contracts import InputFrame
from suika_elika.input.controller import NativeInputRegistry
from suika_elika.input.manager import InputBackend, InputManager


class BattleControls:
    """Poll each physical device once; retain the surviving player's slot.

    A reconnected pad gets a new instance ID. Its GUID/name is only used to
    reclaim a missing slot, never to merge two identical connected controllers.
    """

    def __init__(
        self, registry: NativeInputRegistry, *, preferred_instances: tuple[int, ...] = ()
    ) -> None:
        self.registry = registry
        self._preferred_instances = preferred_instances
        self.slots: list[int | None] = [None, None]
        self._identities = ["", ""]
        self._managers = (InputManager(), InputManager())

    @property
    def ready(self) -> bool:
        return all(slot in self.registry.devices for slot in self.slots)

    @property
    def missing_players(self) -> str:
        return " e ".join(
            str(index + 1)
            for index, slot in enumerate(self.slots)
            if slot not in self.registry.devices
        )

    def sync(self, *, locked: bool) -> None:
        devices = self.registry.devices
        if not locked:
            ids = list(devices)
            active = self.registry.active_instance_id
            if active in ids:
                ids.remove(active)
                ids.insert(0, active)
            if self._preferred_instances:
                ids = [slot for slot in self._preferred_instances if slot in devices] + [
                    slot for slot in ids if slot not in self._preferred_instances
                ]
            desired: list[int | None] = list(ids[:2])
            desired += [None] * (2 - len(desired))
        else:
            desired = [slot if slot in devices else None for slot in self.slots]
            for index, slot in enumerate(desired):
                if slot is not None:
                    continue
                for candidate_id, device in devices.items():
                    identity = device.guid or device.name
                    if candidate_id not in desired and identity == self._identities[index]:
                        desired[index] = candidate_id
                        break

        for index, instance_id in enumerate(desired):
            if instance_id == self.slots[index]:
                continue
            manager = self._managers[index]
            manager.select_backend(None)
            if instance_id is not None:
                device = devices[instance_id]
                self._identities[index] = device.guid or device.name
                device.reset_edges()
                manager.register_adapter(InputBackend.NATIVE, device)
                manager.select_backend(InputBackend.NATIVE)
            self.slots[index] = instance_id
        if locked and self.ready:
            self._preferred_instances = tuple(slot for slot in self.slots if slot is not None)

    def poll(self, delta_seconds: float) -> tuple[InputFrame, InputFrame]:
        return (
            self._managers[0].poll(delta_seconds).frame,
            self._managers[1].poll(delta_seconds).frame,
        )

    def reset(self) -> None:
        for manager in self._managers:
            manager.reset()
