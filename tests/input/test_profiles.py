from __future__ import annotations

from dataclasses import replace

from suika_elika.contracts.ports import ControllerProfileData
from suika_elika.input.profiles import (
    DEFAULT_BINDINGS,
    ProfileRepository,
    RemapWizard,
    WizardStatus,
    stable_profile_id,
)


def _profile(
    *,
    bindings: tuple[tuple[str, str], ...] = (("drop", "button:old"),),
) -> ControllerProfileData:
    return ControllerProfileData(
        profile_id=stable_profile_id(
            platform="linux", guid="abcd", name="Generic Pad", backend="joystick"
        ),
        name="Generic Pad",
        backend="joystick",
        bindings=bindings,
        platform="linux",
        guid="abcd",
    )


def test_profile_identity_uses_platform_and_guid_without_connection_identity() -> None:
    linux = stable_profile_id(
        platform="Linux", guid="ABCD", name="Pad", backend="joystick"
    )
    assert linux == stable_profile_id(
        platform="linux", guid="abcd", name="pad", backend="Joystick"
    )
    assert linux != stable_profile_id(
        platform="windows", guid="abcd", name="pad", backend="joystick"
    )
    assert linux != stable_profile_id(
        platform="linux", guid="other", name="pad", backend="joystick"
    )


class MemoryPersistence:
    def __init__(self, profiles: tuple[ControllerProfileData, ...] = ()) -> None:
        self.profiles = profiles
        self.last_error: str | None = None
        self.fail_next = False

    def load_profiles(self) -> tuple[ControllerProfileData, ...]:
        return self.profiles

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None:
        self.profiles = profiles
        if self.fail_next:
            self.fail_next = False
            self.last_error = "write failed"
        else:
            self.last_error = None


def test_repository_preserves_previous_profile_when_persistence_fails() -> None:
    previous = _profile()
    store = MemoryPersistence((previous,))
    repository = ProfileRepository(store)
    changed = replace(previous, bindings=(("drop", "button:new"),))
    store.fail_next = True

    assert not repository.save(changed)
    assert repository.profiles == (previous,)
    assert store.load_profiles() == (previous,)
    assert repository.last_error == "write failed"


def test_repository_saves_new_profile_after_success() -> None:
    store = MemoryPersistence()
    repository = ProfileRepository(store)
    profile = _profile()

    assert repository.save(profile)
    assert repository.profiles == (profile,)
    assert store.load_profiles() == (profile,)
    assert repository.last_error is None


def test_wizard_waits_for_neutral_before_each_step_and_captures_one_control() -> None:
    original = _profile()
    wizard = RemapWizard(original, steps=(("drop", False), ("pause", False)))

    assert wizard.update(neutral=False).status is WizardStatus.WAITING_FOR_NEUTRAL
    ready = wizard.update(neutral=True)
    assert ready.status is WizardStatus.WAITING_FOR_INPUT
    assert ready.action == "drop"
    assert wizard.update(neutral=True).status is WizardStatus.WAITING_FOR_INPUT

    captured = wizard.update(neutral=True, activated_controls=("button:1",))
    assert captured.captured_control == "button:1"
    assert captured.status is WizardStatus.WAITING_FOR_NEUTRAL
    assert captured.action == "pause"

    wizard.update(neutral=True)
    ambiguous = wizard.update(
        neutral=True, activated_controls=("button:2", "button:3")
    )
    assert ambiguous.status is WizardStatus.WAITING_FOR_INPUT
    assert wizard.update(
        neutral=True, activated_controls=("button:7",)
    ).status is WizardStatus.COMPLETE
    assert dict(wizard.profile.bindings)["drop"] == "button:1"
    assert dict(wizard.profile.bindings)["pause"] == "button:7"
    assert dict(original.bindings)["drop"] == "button:old"


def test_wizard_can_skip_optional_fine_adjustment() -> None:
    steps = (("drop", False), ("fine_adjust", True))
    wizard = RemapWizard(_profile(), steps=steps)
    wizard.update(neutral=True)
    wizard.update(neutral=True, activated_controls=("button:1",))
    wizard.update(neutral=True)

    result = wizard.update(neutral=False, skip=True)
    assert result.status is WizardStatus.COMPLETE
    assert "fine_adjust" not in dict(wizard.profile.bindings)


def test_wizard_cancel_keeps_original_profile_and_restore_uses_defaults() -> None:
    original = _profile()
    cancelled = RemapWizard(original)
    cancelled.update(neutral=True)
    result = cancelled.update(neutral=False, cancel=True)
    assert result.status is WizardStatus.CANCELLED
    assert cancelled.profile == original

    restored = RemapWizard(original)
    assert restored.update(neutral=False, restore_defaults=True).status is WizardStatus.COMPLETE
    assert restored.profile.bindings == tuple(sorted(DEFAULT_BINDINGS))
