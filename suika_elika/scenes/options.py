"""Settings menu and device-neutral controller profile assistant."""

from __future__ import annotations

from dataclasses import replace
from math import isfinite
from typing import Protocol

from suika_elika.contracts import (
    ControllerProfileData,
    InputAction,
    InputEdge,
    InputFrame,
    SceneTransition,
    SettingsData,
)
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.input.profiles import ProfileRepository, RemapWizard, WizardStatus

from .title import MenuCanvas, MenuItem, MenuScene, MenuSnapshot

_NUMERIC_FIELDS = {
    "master_gain": (0.05, 0.0, 1.0),
    "effects_gain": (0.05, 0.0, 1.0),
    "music_gain": (0.05, 0.0, 1.0),
    "safe_area_fraction": (0.01, 0.0, 0.25),
}
_BOOLEAN_FIELDS = {"effects_reduced", "vibration_enabled", "fullscreen"}
_HITBOX_MIN = 0.5
_HITBOX_MAX = 1.5
_HITBOX_STEP = 0.05


class SettingsPersistence(Protocol):
    def load_settings(self) -> SettingsData | None: ...

    def save_settings(self, settings: SettingsData) -> None: ...


class OptionsScene(MenuScene):
    """Editable options; the caller supplies device-neutral remap samples."""

    def __init__(
        self,
        persistence: SettingsPersistence,
        *,
        return_to: str = "title",
        profile_repository: ProfileRepository | None = None,
        active_profile: ControllerProfileData | None = None,
    ) -> None:
        if return_to not in {"title", "paused"}:
            raise ValueError("options return destination must be title or paused")
        super().__init__(
            "Opções",
            (
                MenuItem("Volume geral", "master_gain"),
                MenuItem("Volume dos efeitos", "effects_gain"),
                MenuItem("Volume da música", "music_gain"),
                MenuItem("Efeitos reduzidos", "effects_reduced"),
                MenuItem("Vibração", "vibration_enabled"),
                MenuItem("Tela cheia", "fullscreen"),
                MenuItem("Área segura", "safe_area_fraction"),
                MenuItem("Ajustar hitboxes", "colliders"),
                MenuItem("Configurar controle", "controls"),
                MenuItem("Voltar", "back"),
            ),
            footer="↑/↓ Selecionar  ·  ←/→ Ajustar  ·  Confirmar  ·  Voltar",
            cancel_destination=return_to,
        )
        self.persistence = persistence
        self.return_to = return_to
        self.settings = persistence.load_settings() or SettingsData()
        self.catalog: FruitCatalog = load_catalog()
        self.profile_repository = profile_repository
        self.active_profile = active_profile or self._find_active_profile()
        self._wizard: RemapWizard | None = None
        self._pending_profile: ControllerProfileData | None = None
        self._wizard_prompt = ""
        self._unsaved = False
        self._collider_menu_active = False
        self._options_selected_index = 0

    def _find_active_profile(self) -> ControllerProfileData | None:
        if self.profile_repository is None:
            return None
        return next(
            (
                profile
                for profile in self.profile_repository.profiles
                if profile.profile_id == self.settings.control_profile_id
            ),
            None,
        )

    @property
    def profile_wizard_active(self) -> bool:
        return self._wizard is not None

    @property
    def snapshot(self) -> MenuSnapshot:
        if self._wizard is not None:
            title = "Configurar controle"
            choices = ("Aguardando controle…", "Cancelar")
            subtitle = self._wizard_prompt or "Siga as instruções para remapear."
            return MenuSnapshot(title, choices, 0, subtitle, "Botão leste: cancelar", self.message)
        if self._collider_menu_active:
            return self._collider_snapshot()

        labels: list[str] = []
        for item in self.items:
            key = item.destination
            if key in _NUMERIC_FIELDS:
                value = getattr(self.settings, key)
                rendered = f"{int(round(value * 100))}%"
                labels.append(f"{item.label}: {rendered}")
            elif key in _BOOLEAN_FIELDS:
                state = "Ligado" if getattr(self.settings, key) else "Desligado"
                labels.append(f"{item.label}: {state}")
            elif key == "controls":
                profile_name = self.active_profile.name if self.active_profile else "sem perfil"
                labels.append(f"{item.label}: {profile_name}")
            else:
                labels.append(item.label)
        return MenuSnapshot(
            self.title,
            tuple(labels),
            self.selected_index,
            subtitle="Configurações locais",
            footer=self.footer,
            message=self.message,
        )

    def draw(self, canvas: MenuCanvas) -> None:
        canvas.draw_menu(self.snapshot)

    def handle_actions(self, frame: InputFrame) -> SceneTransition | None:
        edges = self._fresh_edges(frame)
        if self._wizard is not None:
            for edge in edges:
                if edge.action is InputAction.CANCEL:
                    self.handle_profile_sample(cancel=True)
                    return None
                if edge.action is InputAction.CONFIRM and self._pending_profile is not None:
                    self._save_pending_profile()
                    return None
            return None

        if self._collider_menu_active:
            self._handle_collider_actions(frame, edges)
            return None

        for edge in edges:
            if edge.action is InputAction.NAV_UP:
                self.selected_index = (self.selected_index - 1) % len(self.items)
            elif edge.action is InputAction.NAV_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.items)
            elif edge.action is InputAction.CANCEL:
                return self._save_and_return()
            elif edge.action is InputAction.CONFIRM:
                item = self.items[self.selected_index]
                if item.destination == "back":
                    return self._save_and_return()
                if item.destination == "colliders":
                    self._open_collider_menu()
                    return None
                if item.destination in _BOOLEAN_FIELDS:
                    self.settings = replace(
                        self.settings,
                        effects_reduced=(
                            not self.settings.effects_reduced
                            if item.destination == "effects_reduced"
                            else self.settings.effects_reduced
                        ),
                        vibration_enabled=(
                            not self.settings.vibration_enabled
                            if item.destination == "vibration_enabled"
                            else self.settings.vibration_enabled
                        ),
                        fullscreen=(
                            not self.settings.fullscreen
                            if item.destination == "fullscreen"
                            else self.settings.fullscreen
                        ),
                    )
                    self._unsaved = True
                elif item.destination == "controls":
                    self._start_profile_wizard()
                return None

        if frame.move_x <= -0.55:
            self._adjust_selected(-1)
        elif frame.move_x >= 0.55:
            self._adjust_selected(1)
        return None

    def _adjust_selected(self, direction: int) -> None:
        key = self.items[self.selected_index].destination
        spec = _NUMERIC_FIELDS.get(key)
        if spec is None:
            return
        step, lower, upper = spec
        value = float(getattr(self.settings, key))
        updated = max(lower, min(upper, value + direction * step))
        if not isfinite(updated):
            return
        if key == "master_gain":
            self.settings = replace(self.settings, master_gain=updated)
        elif key == "effects_gain":
            self.settings = replace(self.settings, effects_gain=updated)
        elif key == "music_gain":
            self.settings = replace(self.settings, music_gain=updated)
        else:
            self.settings = replace(self.settings, safe_area_fraction=updated)
        self._unsaved = True
        self.message = ""

    def _open_collider_menu(self) -> None:
        self._options_selected_index = self.selected_index
        self._collider_menu_active = True
        self.selected_index = self.catalog.get("apple").level - 1
        self.message = ""

    def _close_collider_menu(self) -> None:
        self._collider_menu_active = False
        self.selected_index = self._options_selected_index
        self.message = ""

    def _collider_snapshot(self) -> MenuSnapshot:
        scale_by_id = dict(self.settings.fruit_hitbox_scales)
        choices = tuple(
            f"{entry.name}: {scale_by_id.get(entry.fruit_id, 1.0):.0%}"
            for entry in self.catalog.entries
        ) + ("Restaurar padrões", "Voltar às opções")
        fruit_count = len(self.catalog.entries)
        subtitle = "Ajuste aplicado ao iniciar ou reiniciar uma partida."
        if self.selected_index < fruit_count:
            entry = self.catalog.entries[self.selected_index]
            scale = scale_by_id.get(entry.fruit_id, 1.0)
            radius = entry.definition.radius * scale
            subtitle = (
                f"{entry.name}: raio {radius:.1f} · padrão {entry.definition.radius:.1f}"
                " · aplica ao reiniciar"
            )
        return MenuSnapshot(
            "Ajustar hitboxes",
            choices,
            self.selected_index,
            subtitle,
            "←/→ Ajustar · Confirmar · Cancelar: opções",
            self.message,
            preview_fruit_id=(
                self.catalog.entries[self.selected_index].fruit_id
                if self.selected_index < fruit_count
                else None
            ),
            preview_hitbox_scale=(
                scale_by_id.get(
                    self.catalog.entries[self.selected_index].fruit_id, 1.0
                )
                if self.selected_index < fruit_count
                else 1.0
            ),
            preview_base_radius=(
                self.catalog.entries[self.selected_index].definition.radius
                if self.selected_index < fruit_count
                else 0.0
            ),
        )

    def _handle_collider_actions(
        self, frame: InputFrame, edges: tuple[InputEdge, ...]
    ) -> None:
        count = len(self.catalog.entries) + 2
        for edge in edges:
            if edge.action is InputAction.NAV_UP:
                self.selected_index = (self.selected_index - 1) % count
            elif edge.action is InputAction.NAV_DOWN:
                self.selected_index = (self.selected_index + 1) % count
            elif edge.action is InputAction.CANCEL:
                self._close_collider_menu()
                return
            elif edge.action is InputAction.CONFIRM:
                if self.selected_index == len(self.catalog.entries):
                    if self.settings.fruit_hitbox_scales:
                        self.settings = replace(self.settings, fruit_hitbox_scales=())
                        self._unsaved = True
                        self.message = "Tamanhos padrão restaurados."
                elif self.selected_index == count - 1:
                    self._close_collider_menu()
                    return
        if frame.move_x <= -0.55:
            self._adjust_fruit_hitbox(-1)
        elif frame.move_x >= 0.55:
            self._adjust_fruit_hitbox(1)

    def _adjust_fruit_hitbox(self, direction: int) -> None:
        if self.selected_index >= len(self.catalog.entries):
            return
        entry = self.catalog.entries[self.selected_index]
        scales = dict(self.settings.fruit_hitbox_scales)
        current = scales.get(entry.fruit_id, 1.0)
        updated = round(
            max(_HITBOX_MIN, min(_HITBOX_MAX, current + direction * _HITBOX_STEP)),
            2,
        )
        if updated == current:
            self.message = f"Limite da hitbox: {updated:.0%}."
            return
        if updated == 1.0:
            scales.pop(entry.fruit_id, None)
        else:
            scales[entry.fruit_id] = updated
        self.settings = replace(
            self.settings,
            fruit_hitbox_scales=tuple(sorted(scales.items())),
        )
        self._unsaved = True
        self.message = ""

    def _save_and_return(self) -> SceneTransition | None:
        if self._unsaved:
            try:
                self.persistence.save_settings(self.settings)
                persistence_error = getattr(self.persistence, "last_error", None)
                if persistence_error:
                    raise OSError(str(persistence_error))
            except Exception as error:
                self.message = f"Não foi possível salvar: {str(error) or type(error).__name__}"
                return None
            self._unsaved = False
        return SceneTransition(self.return_to)

    def _start_profile_wizard(self) -> None:
        if self.active_profile is None or self.profile_repository is None:
            self.message = "Nenhum perfil ativo para configurar; conecte ou selecione um controle."
            return
        self._wizard = RemapWizard(self.active_profile)
        self._pending_profile = None
        self._wizard_prompt = "Solte todos os controles para começar."
        self.message = ""

    def handle_profile_sample(
        self,
        *,
        neutral: bool = False,
        activated_controls: tuple[str, ...] = (),
        cancel: bool = False,
        restore_defaults: bool = False,
        skip: bool = False,
    ) -> None:
        """Feed raw control identity from the selected adapter, never from Pygame here."""
        if self._wizard is None:
            return
        update = self._wizard.update(
            neutral=neutral,
            activated_controls=activated_controls,
            cancel=cancel,
            restore_defaults=restore_defaults,
            skip=skip,
        )
        self._wizard_prompt = update.prompt
        if update.status is WizardStatus.CANCELLED:
            self._wizard = None
            self._pending_profile = None
            self.message = "Perfil anterior mantido."
        elif update.status is WizardStatus.COMPLETE:
            self._pending_profile = self._wizard.profile

    def _save_pending_profile(self) -> None:
        if self._pending_profile is None or self.profile_repository is None:
            return
        if not self.profile_repository.save(self._pending_profile):
            self.message = f"Não foi possível salvar o perfil: {self.profile_repository.last_error}"
            return
        self.active_profile = self._pending_profile
        self._wizard = None
        self._pending_profile = None
        self.settings = replace(
            self.settings,
            control_profile_id=self.active_profile.profile_id,
        )
        self._unsaved = True
        self.message = "Perfil salvo."


__all__ = ["OptionsScene"]
