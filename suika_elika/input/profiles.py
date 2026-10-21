"""Scene-independent controller profile identity and remapping workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Protocol

from suika_elika.contracts.ports import ControllerProfileData, PersistencePort

DEFAULT_BINDINGS: tuple[tuple[str, str], ...] = (
    ("move_left", "dpad:left"),
    ("move_right", "dpad:right"),
    ("confirm", "button:south"),
    ("cancel", "button:east"),
    ("drop", "button:south"),
    ("pause", "button:start"),
    ("fine_adjust", "button:left_shoulder"),
)

REMAP_STEPS: tuple[tuple[str, bool], ...] = (
    ("move_left", False),
    ("move_right", False),
    ("confirm", False),
    ("cancel", False),
    ("drop", False),
    ("pause", False),
    ("fine_adjust", True),
)


def stable_profile_id(
    *, platform: str, guid: str | None, name: str, backend: str
) -> str:
    """Build a stable profile key without using a per-connection instance ID."""
    platform_key = platform.strip().casefold()
    guid_key = guid.strip().casefold() if guid else ""
    name_key = name.strip().casefold()
    backend_key = backend.strip().casefold()
    if not platform_key or not name_key or not backend_key:
        raise ValueError("platform, name, and backend must not be empty")
    identity = "\0".join((platform_key, guid_key, name_key, backend_key))
    return f"controller-{sha256(identity.encode('utf-8')).hexdigest()[:20]}"


class WizardStatus(str, Enum):
    WAITING_FOR_NEUTRAL = "waiting_for_neutral"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WizardUpdate:
    status: WizardStatus
    action: str | None
    prompt: str
    captured_control: str | None = None


class ProfilePersistence(Protocol):
    """Small persistence boundary used by the profile repository."""

    last_error: str | None

    def load_profiles(self) -> tuple[ControllerProfileData, ...]: ...

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None: ...


class ProfileRepository:
    """Keep the active profile list unchanged unless persistence succeeds."""

    def __init__(self, persistence: PersistencePort | ProfilePersistence) -> None:
        self._persistence = persistence
        self._profiles = persistence.load_profiles()
        self.last_error: str | None = None

    @property
    def profiles(self) -> tuple[ControllerProfileData, ...]:
        return self._profiles

    def save(self, profile: ControllerProfileData) -> bool:
        """Insert or replace a profile, rolling back in-memory storage on failure."""
        previous = self._profiles
        updated = {item.profile_id: item for item in previous}
        updated[profile.profile_id] = profile
        candidate = tuple(updated[key] for key in sorted(updated))
        self.last_error = None
        try:
            self._persistence.save_profiles(candidate)
            persistence_error = getattr(self._persistence, "last_error", None)
            if persistence_error:
                raise OSError(str(persistence_error))
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            try:
                self._persistence.save_profiles(previous)
            except Exception:
                pass
            return False
        self._profiles = candidate
        return True


class RemapWizard:
    """Pure remapping state machine; device adapters feed neutral/input samples."""

    def __init__(
        self,
        original: ControllerProfileData,
        *,
        steps: tuple[tuple[str, bool], ...] = REMAP_STEPS,
        defaults: tuple[tuple[str, str], ...] = DEFAULT_BINDINGS,
    ) -> None:
        if not steps or any(not action for action, _optional in steps):
            raise ValueError("wizard steps must contain named actions")
        if len({action for action, _optional in steps}) != len(steps):
            raise ValueError("wizard action steps must be unique")
        self.original = original
        self.steps = steps
        self.defaults = defaults
        self._bindings = dict(original.bindings)
        self._index = 0
        self._status = WizardStatus.WAITING_FOR_NEUTRAL
        self._neutral_seen = False

    @property
    def status(self) -> WizardStatus:
        return self._status

    @property
    def profile(self) -> ControllerProfileData:
        """Return the proposed profile; it is not persisted until the caller saves it."""
        bindings = self.original.bindings
        if self._status is WizardStatus.COMPLETE:
            bindings = tuple(sorted(self._bindings.items()))
        return ControllerProfileData(
            profile_id=self.original.profile_id,
            name=self.original.name,
            backend=self.original.backend,
            bindings=bindings,
            platform=self.original.platform,
            guid=self.original.guid,
            axes=self.original.axes,
            inverted_axes=self.original.inverted_axes,
            deadzone=self.original.deadzone,
            sensitivity=self.original.sensitivity,
        )

    def update(
        self,
        *,
        neutral: bool,
        activated_controls: tuple[str, ...] = (),
        cancel: bool = False,
        restore_defaults: bool = False,
        skip: bool = False,
    ) -> WizardUpdate:
        """Advance using a device-neutral sample from an SDL or test adapter."""
        if self._status in (WizardStatus.COMPLETE, WizardStatus.CANCELLED):
            return self._result()
        if cancel:
            self._status = WizardStatus.CANCELLED
            return self._result()
        if restore_defaults:
            self._bindings = dict(self.defaults)
            self._status = WizardStatus.COMPLETE
            return self._result()

        action, optional = self.steps[self._index]
        if skip:
            if not optional:
                return self._result()
            self._index += 1
            self._advance_status()
            return self._result()

        if not self._neutral_seen:
            if neutral:
                self._neutral_seen = True
                self._status = WizardStatus.WAITING_FOR_INPUT
            return self._result()

        controls = tuple(control for control in activated_controls if control)
        if len(controls) != 1:
            return self._result()
        self._bindings[action] = controls[0]
        captured = controls[0]
        self._index += 1
        self._advance_status()
        return self._result(captured_control=captured)

    def _advance_status(self) -> None:
        self._neutral_seen = False
        if self._index >= len(self.steps):
            self._status = WizardStatus.COMPLETE
        else:
            self._status = WizardStatus.WAITING_FOR_NEUTRAL

    def _result(self, captured_control: str | None = None) -> WizardUpdate:
        action = (
            self.steps[self._index][0]
            if self._status in (
                WizardStatus.WAITING_FOR_NEUTRAL,
                WizardStatus.WAITING_FOR_INPUT,
            )
            else None
        )
        if self._status is WizardStatus.WAITING_FOR_NEUTRAL:
            prompt = f"Solte todos os controles para continuar: {action}"
        elif self._status is WizardStatus.WAITING_FOR_INPUT:
            prompt = f"Acione o controle para: {action}"
        elif self._status is WizardStatus.COMPLETE:
            prompt = "Remapeamento concluído; confirme para salvar."
        else:
            prompt = "Remapeamento cancelado; o perfil anterior foi mantido."
        return WizardUpdate(self._status, action, prompt, captured_control)
