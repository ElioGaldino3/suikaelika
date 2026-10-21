from __future__ import annotations

import pytest

from suika_elika.contracts import (
    ControllerProfileData,
    InputAction,
    InputEdge,
    InputFrame,
    SettingsData,
)
from suika_elika.input.profiles import ProfileRepository
from suika_elika.scenes.help import HelpScene
from suika_elika.scenes.options import OptionsScene
from suika_elika.scenes.pause import PauseScene
from suika_elika.scenes.results import ResultsScene, ResultSummary
from suika_elika.scenes.title import MenuSnapshot, TitleScene


class FakePersistence:
    def __init__(self, settings: SettingsData | None = None) -> None:
        self.settings = settings
        self.profiles: tuple[ControllerProfileData, ...] = ()
        self.settings_saved: list[SettingsData] = []
        self.profiles_saved: list[tuple[ControllerProfileData, ...]] = []
        self.last_error: str | None = None
        self.fail_settings = False

    def load_settings(self) -> SettingsData | None:
        return self.settings

    def save_settings(self, settings: SettingsData) -> None:
        self.settings_saved.append(settings)
        if self.fail_settings:
            self.last_error = "disco cheio"
            return
        self.settings = settings
        self.last_error = None

    def load_profiles(self) -> tuple[ControllerProfileData, ...]:
        return self.profiles

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None:
        self.profiles_saved.append(profiles)
        self.profiles = profiles
        self.last_error = None


class FakeCanvas:
    def __init__(self) -> None:
        self.snapshot: MenuSnapshot | None = None

    def draw_menu(self, snapshot: MenuSnapshot) -> None:
        self.snapshot = snapshot


def _frame(sequence: int, action: InputAction, *, move_x: float = 0.0) -> InputFrame:
    return InputFrame(move_x=move_x, edges=(InputEdge(sequence, action),))


def _profile() -> ControllerProfileData:
    return ControllerProfileData(
        profile_id="pad-xbox",
        name="Controle Xbox",
        backend="controller",
        platform="linux",
        guid="abc",
        bindings=(
            ("move_left", "dpad:left"),
            ("move_right", "dpad:right"),
            ("confirm", "button:south"),
            ("cancel", "button:east"),
            ("drop", "button:south"),
            ("pause", "button:start"),
            ("fine_adjust", "button:left_shoulder"),
        ),
    )


def test_title_menu_uses_semantic_navigation_and_describes_physical_confirm() -> None:
    scene = TitleScene(controller_status="Controle conectado")
    scene.handle_actions(_frame(1, InputAction.NAV_DOWN))
    assert scene.snapshot.selected_index == 1

    scene.handle_actions(_frame(2, InputAction.NAV_DOWN))

    transition = scene.handle_actions(_frame(3, InputAction.CONFIRM))
    assert transition is not None
    assert transition.destination == "help"
    assert transition.payload == (("return_to", "title"),)
    assert "botão sul" in scene.snapshot.footer
    assert "Nintendo" in scene.snapshot.footer


def test_replayed_edge_sequence_does_not_confirm_again() -> None:
    scene = TitleScene()
    edge = InputFrame(edges=(InputEdge(10, InputAction.CONFIRM),))
    assert scene.handle_actions(edge).destination == "play"  # type: ignore[union-attr]
    assert scene.handle_actions(edge) is None


@pytest.mark.parametrize("return_to", ["title", "paused"])
def test_help_returns_only_to_its_origin(return_to: str) -> None:
    scene = HelpScene(return_to=return_to)
    assert "mova a mira" in scene.snapshot.subtitle.casefold()
    assert "segure para repetir a 180 BPM" in scene.snapshot.subtitle

    transition = scene.handle_actions(_frame(1, InputAction.CANCEL))
    assert transition is not None and transition.destination == return_to
    assert scene.handle_actions(_frame(1, InputAction.CONFIRM)) is None


def test_pause_requires_confirmation_and_focuses_cancel_by_default() -> None:
    scene = PauseScene()
    scene.handle_actions(_frame(1, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(2, InputAction.CONFIRM))
    assert scene.snapshot.choices == ("Sim", "Cancelar")
    assert scene.snapshot.selected_index == 1

    # Cancel leaves the current round intact and the same edge cannot confirm elsewhere.
    scene.handle_actions(_frame(3, InputAction.CANCEL))
    assert scene.confirmation is None
    assert scene.handle_actions(_frame(3, InputAction.CONFIRM)) is None

    scene.handle_actions(_frame(4, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(5, InputAction.CONFIRM))
    assert scene.confirmation == "restart"
    scene.handle_actions(_frame(6, InputAction.NAV_UP))
    transition = scene.handle_actions(_frame(7, InputAction.CONFIRM))
    assert transition is not None and transition.destination == "play"
    assert transition.payload == (("restart", True),)


def test_pause_abandonment_is_also_confirmed() -> None:
    scene = PauseScene()
    for sequence in range(1, 4):
        scene.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(4, InputAction.CONFIRM))
    assert scene.confirmation == "abandon"
    assert scene.snapshot.selected_index == 1
    scene.handle_actions(_frame(5, InputAction.NAV_UP))
    transition = scene.handle_actions(_frame(6, InputAction.CONFIRM))
    assert transition is not None and transition.destination == "title"
    assert transition.payload == (("abandoned", True),)


def test_options_save_changes_and_return_to_the_origin() -> None:
    persistence = FakePersistence(SettingsData())
    scene = OptionsScene(persistence, return_to="paused")
    for sequence in range(1, 4):
        scene.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(4, InputAction.CONFIRM))  # Toggle effects reduced.
    assert scene.settings.effects_reduced
    transition = scene.handle_actions(_frame(5, InputAction.CANCEL))

    assert transition is not None and transition.destination == "paused"
    assert persistence.settings_saved == [scene.settings]


def test_options_adjustment_is_clamped_and_save_failure_stays_on_screen() -> None:
    persistence = FakePersistence(SettingsData(safe_area_fraction=0.25))
    persistence.fail_settings = True
    scene = OptionsScene(persistence)
    for sequence in range(1, 7):
        scene.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    scene.handle_actions(InputFrame(move_x=1.0))
    assert scene.settings.safe_area_fraction == pytest.approx(0.25)

    transition = scene.handle_actions(_frame(7, InputAction.CANCEL))
    assert transition is None
    assert "disco cheio" in scene.message
    assert "Área segura: 25%" in scene.snapshot.choices[6]


def test_collider_menu_adjusts_apple_and_saves_the_scale() -> None:
    persistence = FakePersistence(SettingsData())
    scene = OptionsScene(persistence, return_to="paused")
    for sequence in range(1, 8):
        scene.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(8, InputAction.CONFIRM))

    assert scene.snapshot.title == "Ajustar hitboxes"
    assert scene.snapshot.selected_index == 4
    assert scene.snapshot.choices[4] == "Maçã: 100%"
    scene.handle_actions(InputFrame(move_x=1.0))
    assert scene.snapshot.choices[4] == "Maçã: 105%"
    assert "37.8" in scene.snapshot.subtitle

    scene.handle_actions(_frame(9, InputAction.CANCEL))
    assert scene.snapshot.title == "Opções"
    transition = scene.handle_actions(_frame(10, InputAction.CANCEL))

    assert transition is not None and transition.destination == "paused"
    assert persistence.settings_saved[-1].fruit_hitbox_scales == (("apple", 1.05),)


def test_controller_assistant_requires_neutral_and_explicit_save_confirmation() -> None:
    persistence = FakePersistence(SettingsData(control_profile_id="pad-xbox"))
    persistence.profiles = (_profile(),)
    repository = ProfileRepository(persistence)
    scene = OptionsScene(persistence, profile_repository=repository)

    # Move focus from master volume to the profile assistant.
    for sequence in range(1, 9):
        scene.handle_actions(_frame(sequence, InputAction.NAV_DOWN))
    scene.handle_actions(_frame(9, InputAction.CONFIRM))
    assert scene.profile_wizard_active

    for index in range(7):
        scene.handle_profile_sample(neutral=True)
        scene.handle_profile_sample(activated_controls=(f"button:{index}",))
    assert "confirme para salvar" in scene.snapshot.subtitle.casefold()
    assert persistence.profiles_saved == []

    scene.handle_actions(_frame(10, InputAction.CONFIRM))
    assert not scene.profile_wizard_active
    assert persistence.profiles_saved
    assert scene.active_profile is not None
    assert dict(scene.active_profile.bindings)["confirm"] == "button:2"


def test_results_show_counters_and_offer_replay_or_menu() -> None:
    scene = ResultsScene(ResultSummary(42, 100, 6, 2, 95.0))
    assert "Pontos: 42" in scene.snapshot.subtitle
    assert "Melancias: 2" in scene.snapshot.subtitle
    transition = scene.handle_actions(_frame(1, InputAction.CONFIRM))
    assert transition is not None and transition.destination == "play"
    assert transition.payload == (("restart", True),)


def test_result_summary_rejects_invalid_counters() -> None:
    with pytest.raises(ValueError):
        ResultSummary(-1, 0, 0, 0, 0)
