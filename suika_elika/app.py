"""Pygame composition root and bounded fixed-step application loop."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from suika_elika.audio import create_audio_manager
from suika_elika.config import AppConfig
from suika_elika.contracts import (
    InputAction,
    InputEdge,
    InputFrame,
    RoundState,
    SceneTransition,
    SettingsData,
)
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.game.physics import PhysicsConfig, PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.input.battle import BattleControls
from suika_elika.input.controller import NativeInputRegistry
from suika_elika.input.manager import InputBackend, InputManager, InputSample
from suika_elika.persistence import JsonPersistence
from suika_elika.rendering.assets import ASSET_ROOT, cover_surface
from suika_elika.rendering.battle import BattleRenderer
from suika_elika.rendering.renderer import Renderer
from suika_elika.scene_manager import SceneManager


class _KeyboardAdapter:
    """Keyboard controls for development, enabled as one exclusive backend."""

    def __init__(self, pygame_module: Any) -> None:
        self.pygame = pygame_module
        self._edges: list[InputAction] = []

    def process_events(self, events: tuple[Any, ...]) -> None:
        keys = self.pygame
        mapping = {
            getattr(keys, "K_RETURN", -1): (InputAction.CONFIRM, InputAction.DROP),
            getattr(keys, "K_SPACE", -2): (InputAction.DROP,),
            getattr(keys, "K_ESCAPE", -3): (InputAction.PAUSE, InputAction.CANCEL),
            getattr(keys, "K_p", -4): (InputAction.PAUSE,),
        }
        keydown = getattr(keys, "KEYDOWN", object())
        for event in events:
            if getattr(event, "type", None) == keydown and not getattr(event, "repeat", False):
                self._edges.extend(mapping.get(getattr(event, "key", None), ()))

    def poll(self) -> InputSample:
        keys = self.pygame.key.get_pressed()
        left = bool(keys[self.pygame.K_LEFT])
        right = bool(keys[self.pygame.K_RIGHT])
        up = bool(keys[self.pygame.K_UP])
        down = bool(keys[self.pygame.K_DOWN])
        fine = bool(keys[self.pygame.K_LSHIFT])
        edges = tuple(self._edges)
        self._edges.clear()
        return InputSample(
            left=left,
            right=right,
            up=up,
            down=down,
            fine_adjust=fine,
            action_edges=edges,
            drop_held=bool(keys[self.pygame.K_SPACE] or keys[self.pygame.K_RETURN]),
        )

    def clear(self) -> None:
        self._edges.clear()


class _MenuCanvas:
    """Small native Pygame renderer for the text-only scene contracts."""

    def __init__(self, pygame_module: Any, target: Any) -> None:
        self.pygame = pygame_module
        self.target = target
        if not self.pygame.font.get_init():
            self.pygame.font.init()
        menu_path = ASSET_ROOT / "backgrounds" / "menu.png"
        self._background = (
            self.pygame.image.load(menu_path) if menu_path.is_file() else None
        )
        self._scaled_background: Any = None
        self._scaled_size: tuple[int, int] | None = None
        self._panel: Any = None
        self._panel_size: tuple[int, int] | None = None

    def draw_menu(self, snapshot: Any) -> None:
        surface = self.target
        width, height = surface.get_size()
        footer_lines = sum(bool(line) for line in (snapshot.message, snapshot.footer))
        layout = calculate_menu_layout(
            height,
            subtitle_lines=len(snapshot.subtitle.splitlines()),
            choice_count=len(snapshot.choices),
            footer_lines=footer_lines,
        )
        if self._background is None:
            surface.fill((112, 201, 235))
        else:
            if self._scaled_size != (width, height):
                self._scaled_background = cover_surface(
                    self.pygame, self._background, (width, height)
                )
                self._scaled_size = (width, height)
            surface.blit(self._scaled_background, (0, 0))
        if self._panel_size != (width, height):
            self._panel = self.pygame.Surface(
                (width, height), self.pygame.SRCALPHA, 32
            )
            panel_rect = self.pygame.Rect(
                round(width * 0.12),
                round(height * 0.07),
                round(width * 0.76),
                round(height * 0.86),
            )
            self.pygame.draw.rect(
                self._panel, (15, 53, 63, 172), panel_rect, border_radius=24
            )
            self._panel_size = (width, height)
        surface.blit(self._panel, (0, 0))
        title_font = self.pygame.font.Font(None, layout.title_font_size)
        body_font = self.pygame.font.Font(None, layout.body_font_size)
        small_font = self.pygame.font.Font(None, layout.footer_font_size)
        title = title_font.render(snapshot.title, True, (255, 247, 220))
        surface.blit(title, title.get_rect(center=(width // 2, layout.title_y)))

        for index, line in enumerate(snapshot.subtitle.splitlines()):
            rendered = small_font.render(line, True, (235, 247, 239))
            subtitle_y = layout.subtitle_y + index * layout.subtitle_spacing
            surface.blit(rendered, rendered.get_rect(center=(width // 2, subtitle_y)))

        for index, label in enumerate(snapshot.choices):
            selected = index == snapshot.selected_index
            disabled = index in snapshot.disabled_indices
            color = (145, 155, 157) if disabled else (
                (255, 229, 121) if selected else (255, 247, 220)
            )
            text = body_font.render(("›  " if selected else "   ") + label, True, color)
            item_y = layout.choices_y + index * layout.choice_spacing
            surface.blit(text, text.get_rect(center=(width // 2, round(item_y))))

        footer_text = [line for line in (snapshot.message, snapshot.footer) if line]
        first_footer_y = layout.footer_y - (len(footer_text) - 1) * layout.footer_spacing
        for index, line in enumerate(footer_text):
            rendered = small_font.render(line, True, (235, 247, 239))
            footer_y = first_footer_y + index * layout.footer_spacing
            surface.blit(rendered, rendered.get_rect(center=(width // 2, footer_y)))


@dataclass(frozen=True, slots=True)
class _MenuLayout:
    title_y: int
    title_font_size: int
    subtitle_y: int
    subtitle_spacing: int
    choices_y: float
    choice_spacing: float
    body_font_size: int
    footer_y: int
    footer_spacing: int
    footer_font_size: int


def calculate_menu_layout(
    height: int,
    *,
    subtitle_lines: int,
    choice_count: int,
    footer_lines: int,
) -> _MenuLayout:
    """Fit menu rows between the subtitle and footer at common TV resolutions."""
    if (
        type(height) is not int
        or height <= 0
        or any(type(value) is not int or value < 0 for value in (subtitle_lines, footer_lines))
        or type(choice_count) is not int
        or choice_count <= 0
    ):
        raise ValueError("menu dimensions and row counts are invalid")

    title_y = int(height * 0.18)
    title_font_size = max(32, min(72, int(height * 0.10)))
    subtitle_y = int(height * 0.29)
    subtitle_spacing = max(18, min(30, int(height * 0.042)))
    footer_font_size = max(16, min(25, int(height * 0.035)))
    footer_spacing = max(18, min(28, int(footer_font_size * 1.12)))
    footer_y = height - max(18, int(height * 0.045))
    footer_top = footer_y - max(0, footer_lines - 1) * footer_spacing

    choices_top = max(
        int(height * 0.43),
        subtitle_y + subtitle_lines * subtitle_spacing + 12,
    )
    choices_bottom = max(choices_top, footer_top - 16)
    available = choices_bottom - choices_top
    if choice_count == 1:
        choice_spacing = 0.0
        choices_y = (choices_top + choices_bottom) / 2
        body_font_size = max(20, min(38, int(height * 0.053)))
    else:
        choice_spacing = min(56.0, available / (choice_count - 1))
        used = choice_spacing * (choice_count - 1)
        choices_y = choices_top + (available - used) / 2
        body_font_size = max(18, min(38, int(choice_spacing * 0.78)))

    return _MenuLayout(
        title_y=title_y,
        title_font_size=title_font_size,
        subtitle_y=subtitle_y,
        subtitle_spacing=subtitle_spacing,
        choices_y=choices_y,
        choice_spacing=choice_spacing,
        body_font_size=body_font_size,
        footer_y=footer_y,
        footer_spacing=footer_spacing,
        footer_font_size=footer_font_size,
    )


class App:
    """Initialize devices, compose services, run, and release Pygame cleanly."""

    def __init__(
        self, config: AppConfig | None = None, *, pygame_module: Any | None = None
    ) -> None:
        self.config = config or AppConfig()
        self._pygame = pygame_module
        self._accumulator = 0.0
        self._exit_code = 0
        self._focus_lock = False
        self._focus_resume_gameplay = False
        self._focused = True
        self._closed = False
        self._settings = SettingsData(fullscreen=self.config.fullscreen)
        self._applied_settings: SettingsData | None = None
        self._registry: NativeInputRegistry | None = None
        self._keyboard: _KeyboardAdapter | None = None
        self._selected_controller_identity: str | None = None
        self._controller_reconnect_lock = False
        self._controller_resume_gameplay = False
        self._input = InputManager()
        self._audio: Any = None
        self._persistence: Any = None
        self._session: GameSession | None = None
        self._manager: SceneManager | None = None
        self._screen: Any = None
        self._renderer: Renderer | None = None
        self._battle_renderer: BattleRenderer | None = None
        self._battle_controls: BattleControls | None = None
        self._battle_connection_lock = False
        self._battle_resume_gameplay = False
        self._battle_focus_resume = False
        self._battle_menu_sequence = 0
        self._menu_canvas: _MenuCanvas | None = None
        self._clock: Any = None

    @property
    def scene_manager(self) -> SceneManager | None:
        return self._manager

    @property
    def accumulator(self) -> float:
        return self._accumulator

    def run(self, *, frame_limit: int | None = None) -> int:
        """Run until the scene requests exit, the window closes, or test limit hits."""
        if frame_limit is not None and (type(frame_limit) is not int or frame_limit < 0):
            raise ValueError("frame_limit must be a non-negative integer or None")
        pygame = self._pygame
        if pygame is None:
            try:
                import pygame as pygame_module
            except ImportError:
                return 1
            pygame = pygame_module
            self._pygame = pygame

        try:
            pygame.init()
            self._initialize_runtime()
            frame_number = 0
            previous_ticks = pygame.time.get_ticks() / 1000.0
            while self._manager is not None and self._manager.running:
                elapsed = self._clock.tick(self.config.target_fps) / 1000.0
                now = pygame.time.get_ticks() / 1000.0
                ui_delta = max(
                    0.0,
                    min(self.config.max_frame_delta, elapsed or now - previous_ticks),
                )
                previous_ticks = now
                events = tuple(pygame.event.get())
                if any(event.type == pygame.QUIT for event in events):
                    break
                self._process_events(events)
                self._update_focus()
                if not self._focus_lock:
                    self._poll_and_dispatch(ui_delta, events)
                    self._advance_simulation(ui_delta)
                    self._manager.update(ui_delta)
                    self._apply_current_settings()
                else:
                    self._poll_focus_confirmation(ui_delta, events)
                    self._manager.update(ui_delta)
                self._draw()
                pygame.display.flip()
                frame_number += 1
                if frame_limit is not None and frame_number >= frame_limit:
                    break
        except Exception as error:
            print(f"Suika Elika: {error}", file=sys.stderr)
            self._exit_code = 1
        finally:
            self.close()
        return self._exit_code

    def close(self) -> None:
        """Release opened controllers/audio and let Pygame release its subsystems."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._manager is not None:
                try:
                    self._manager.current.exit()
                except Exception:
                    self._exit_code = 1
            if self._registry is not None:
                try:
                    self._registry.close()
                except Exception:
                    self._exit_code = 1
            if self._audio is not None:
                try:
                    self._audio.close()
                except Exception:
                    self._exit_code = 1
        finally:
            if self._pygame is not None:
                try:
                    self._pygame.quit()
                except Exception:
                    self._exit_code = 1

    def _initialize_runtime(self) -> None:
        pygame = self._pygame
        assert pygame is not None
        self._persistence = JsonPersistence()
        self._settings = self._persistence.load_settings() or SettingsData(
            fullscreen=self.config.fullscreen
        )
        catalog = self._catalog_for_settings(self._settings)
        self._create_display()

        self._registry = NativeInputRegistry(pygame)
        devices = self._registry.discover()
        preferred: tuple[int, ...] = ()
        if self.config.player_indexes is not None:
            by_index = {
                device.device_index: instance_id
                for instance_id, device in self._registry.devices.items()
            }
            missing = [index for index in self.config.player_indexes if index not in by_index]
            if missing:
                raise ValueError(f"Controles não disponíveis nos índices: {missing}")
            preferred = tuple(by_index[index] for index in self.config.player_indexes)
            devices = preferred + tuple(
                instance for instance in devices if instance not in preferred
            )
        self._battle_controls = BattleControls(self._registry, preferred_instances=preferred)
        if self.config.allow_keyboard_fallback:
            self._keyboard = _KeyboardAdapter(pygame)
            self._input.register_adapter(InputBackend.KEYBOARD_EMULATED, self._keyboard)
        if devices:
            self._registry.select(devices[0])
            self._selected_controller_identity = self._controller_identity(
                self._registry.devices.get(devices[0])
            )
            self._input.register_adapter(InputBackend.NATIVE, self._registry)
            self._input.select_backend(InputBackend.NATIVE)
            controller_status = "Controle conectado"
        else:
            controller_status = "Controle não conectado"
            if self.config.allow_keyboard_fallback:
                self._input.select_backend(InputBackend.KEYBOARD_EMULATED)
                controller_status += " · teclado de desenvolvimento"
        self._battle_controls.sync(locked=False)

        self._session = GameSession(
            PhysicsWorld(PhysicsConfig(fixed_dt=self.config.fixed_dt)),
            catalog=catalog,
            persistence=self._persistence,
            fixed_dt=self.config.fixed_dt,
        )
        self._audio = create_audio_manager(pygame)
        self._audio.set_gains(
            master=self._settings.master_gain,
            effects=self._settings.effects_gain,
            music=self._settings.music_gain,
        )
        self._applied_settings = self._settings
        self._renderer = Renderer(
            self._screen,
            safe_area_fraction=self._settings.safe_area_fraction,
            reduced_effects=self._settings.effects_reduced,
            debug_colliders=self.config.debug_colliders,
        )
        self._menu_canvas = _MenuCanvas(pygame, self._screen)
        self._battle_renderer = BattleRenderer(
            self._screen, safe_area_fraction=self._settings.safe_area_fraction,
            reduced_effects=self._settings.effects_reduced,
            debug_colliders=self.config.debug_colliders,
        )
        self._clock = pygame.time.Clock()
        self._manager = SceneManager(
            self._session,
            self._persistence,
            self._input,
            self._audio,
            controller_status=controller_status,
            fixed_dt=self.config.fixed_dt,
            keyboard_enabled=self.config.allow_keyboard_fallback,
            catalog_provider=self._load_saved_catalog,
        )
        self._renderer.set_catalog(self._session.catalog)
        self._battle_renderer.set_catalog(
            self._manager.battle_session.players[0].catalog
        )
        self._manager.set_controller_count(len(self._registry.devices))

    def _catalog_for_settings(self, settings: SettingsData) -> FruitCatalog:
        catalog = load_catalog()
        known_ids = {entry.fruit_id for entry in catalog.entries}
        scales = tuple(
            (fruit_id, scale)
            for fruit_id, scale in settings.fruit_hitbox_scales
            if fruit_id in known_ids
        )
        return catalog.with_hitbox_scales(scales)

    def _load_saved_catalog(self) -> FruitCatalog:
        settings = (
            self._persistence.load_settings()
            if self._persistence is not None
            else None
        )
        return self._catalog_for_settings(settings or self._settings)

    def _create_display(self) -> None:
        pygame = self._pygame
        assert pygame is not None
        flags = pygame.FULLSCREEN if self._settings.fullscreen else 0
        # A zero size asks SDL for the current desktop resolution in fullscreen.
        size = (0, 0) if self._settings.fullscreen else self.config.window_size
        self._screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("Suika Elika")

    def _process_events(self, events: tuple[Any, ...]) -> None:
        if self._registry is not None:
            active_before = self._registry.active_instance_id
            added = self._registry.process_events(events)
            battle_mode = self._manager is not None and self._manager.battle_mode
            if self._battle_controls is not None:
                self._battle_controls.sync(locked=battle_mode)
            if self._manager is not None:
                self._manager.set_controller_count(len(self._registry.devices))
            if battle_mode:
                self._update_battle_connection()
            elif active_before is not None and self._registry.active_instance_id is None:
                self._handle_active_controller_removal()
            elif (
                not self._controller_reconnect_lock
                and self._registry.active_instance_id is None and self._registry.devices
            ):
                selected_id = next(iter(self._registry.devices))
                self._registry.select(selected_id)
                self._input.register_adapter(InputBackend.NATIVE, self._registry)
                self._input.select_backend(InputBackend.NATIVE)
                self._selected_controller_identity = self._controller_identity(
                    self._registry.devices[selected_id]
                )
            if self._controller_reconnect_lock:
                for instance_id in added:
                    device = self._registry.devices.get(instance_id)
                    identity = self._controller_identity(device)
                    if (
                        identity is None
                        or identity != self._selected_controller_identity
                    ):
                        continue
                    self._registry.select(instance_id)
                    self._input.select_backend(InputBackend.NATIVE)
                    break
        if self._keyboard is not None:
            self._keyboard.process_events(events)
        pygame = self._pygame
        assert pygame is not None
        if any(event.type == getattr(pygame, "WINDOWFOCUSLOST", -1) for event in events):
            self._lose_focus()
        if any(event.type == getattr(pygame, "WINDOWFOCUSGAINED", -1) for event in events):
            self._focused = True

    def _update_focus(self) -> None:
        pygame = self._pygame
        assert pygame is not None
        getter = getattr(pygame.key, "get_focused", None)
        if callable(getter):
            focused = bool(getter())
            if not focused:
                self._lose_focus()
            elif self._focus_lock:
                self._focused = True

    def _lose_focus(self) -> None:
        if self._focus_lock:
            self._focused = False
            return
        self._focused = False
        self._focus_lock = True
        self._accumulator = 0.0
        if self._manager is not None and self._manager.current_name == "battle":
            self._battle_focus_resume = not self._battle_connection_lock
            self._manager.battle_session.pause()
        self._focus_resume_gameplay = (
            self._manager is not None
            and self._manager.current_name == "play"
            and self._session is not None
            and self._session.round_state in (RoundState.READY, RoundState.PLAYING)
        )
        if self._session is not None and self._session.round_state in (
            RoundState.READY,
            RoundState.PLAYING,
        ):
            self._session.pause()
        if self._audio is not None:
            self._audio.pause()
        self._clear_input_states()
        if self._manager is not None:
            self._manager.reset_input()

    def _clear_input_states(self) -> None:
        self._input.reset()
        if self._battle_controls is not None:
            self._battle_controls.reset()
        if self._keyboard is not None:
            self._keyboard.clear()
        if self._registry is not None:
            for adapter in self._registry.devices.values():
                reset = getattr(adapter, "reset_edges", None)
                if callable(reset):
                    reset()

    def _handle_active_controller_removal(self) -> None:
        """Pause and disarm the active player until its controller is confirmed again."""
        self._controller_reconnect_lock = True
        self._controller_resume_gameplay = (
            self._manager is not None
            and self._manager.current_name == "play"
            and self._session is not None
            and self._session.round_state in (RoundState.READY, RoundState.PLAYING)
        )
        if self._session is not None and self._controller_resume_gameplay:
            self._session.pause()
        if self._audio is not None:
            self._audio.pause()
        self._accumulator = 0.0
        self._input.select_backend(None)
        self._clear_input_states()
        if self._registry is not None:
            self._registry.select(None)
        if self._keyboard is not None:
            self._input.select_backend(InputBackend.KEYBOARD_EMULATED)
        if self._manager is not None:
            self._manager.reset_input()

    def _poll_and_dispatch(self, ui_delta: float, events: tuple[Any, ...]) -> None:
        del events
        assert self._manager is not None
        if self._manager.battle_mode and self._battle_controls is not None:
            frames = self._battle_controls.poll(ui_delta)
            if self._battle_connection_lock:
                if any(edge.action is InputAction.CANCEL for f in frames for edge in f.edges):
                    self._manager.transition(SceneTransition("title"))
                    self._battle_connection_lock = False
                    self._battle_resume_gameplay = False
                    self._clear_input_states()
                elif self._battle_controls.ready and any(
                    edge.action is InputAction.CONFIRM for f in frames for edge in f.edges
                ):
                    self._battle_connection_lock = False
                    self._clear_input_states()
                    self._manager.reset_input()
                    if self._battle_resume_gameplay:
                        self._manager.battle_session.resume()
                        self._audio.resume()
                    self._battle_resume_gameplay = False
                return
            if self._manager.current_name == "battle":
                self._manager.handle_battle_actions(frames)
            else:
                # Both players may navigate shared battle menus. One source per
                # frame prevents a simultaneous confirm from choosing two items.
                frame = frames[0] if (
                    frames[0].edges or frames[0].move_x or frames[0].move_y
                ) else frames[1]
                edges = []
                for edge in frame.edges:
                    edges.append(InputEdge(self._battle_menu_sequence, edge.action))
                    self._battle_menu_sequence += 1
                self._manager.handle_actions(InputFrame(
                    move_x=frame.move_x, move_y=frame.move_y,
                    fine_adjust=frame.fine_adjust, edges=tuple(edges),
                ))
            return
        managed = self._input.poll(ui_delta)
        if self._controller_reconnect_lock:
            confirmed = any(
                edge.action is InputAction.CONFIRM for edge in managed.frame.edges
            )
            if (
                confirmed
                and self._registry is not None
                and (
                    self._registry.active_instance_id is not None
                    or self._input.active_backend is InputBackend.KEYBOARD_EMULATED
                )
            ):
                self._controller_reconnect_lock = False
                self._input.reset()
                if self._controller_resume_gameplay and self._session is not None:
                    self._session.resume()
                if self._controller_resume_gameplay and self._audio is not None:
                    self._audio.resume()
                self._controller_resume_gameplay = False
            # Confirmation is consumed here. In particular, a face button mapped
            # to CONFIRM and DROP cannot resume and launch in the same frame.
            return
        self._manager.handle_actions(managed.frame)
        if self._manager.current_name == "battle":
            # Player two may have held a button while player one chose the mode.
            self._clear_input_states()
            self._manager.reset_input()

    def _poll_focus_confirmation(self, ui_delta: float, events: tuple[Any, ...]) -> None:
        del events
        if (
            self._manager is not None and self._manager.battle_mode
            and self._battle_controls is not None
        ):
            frames = self._battle_controls.poll(ui_delta)
            if not self._focused or not any(
                edge.action is InputAction.CONFIRM for f in frames for edge in f.edges
            ):
                return
            self._focus_lock = False
            self._accumulator = 0.0
            self._clear_input_states()
            self._manager.reset_input()
            if self._battle_focus_resume and not self._battle_connection_lock:
                self._manager.battle_session.resume()
                self._audio.resume()
            self._battle_focus_resume = False
            return
        managed = self._input.poll(ui_delta)
        if not self._focused or not any(
            edge.action is InputAction.CONFIRM for edge in managed.frame.edges
        ):
            return
        self._focus_lock = False
        self._accumulator = 0.0
        self._clear_input_states()
        if self._focus_resume_gameplay and self._session is not None:
            self._session.resume()
        if self._focus_resume_gameplay and self._audio is not None:
            self._audio.resume()
        self._focus_resume_gameplay = False

    def _advance_simulation(self, elapsed: float) -> int:
        if (
            self._manager is None or self._manager.current_name not in {"play", "battle"}
            or self._battle_connection_lock
        ):
            self._accumulator = 0.0
            return 0
        self._accumulator += min(elapsed, self.config.max_frame_delta)
        steps = 0
        while (
            self._accumulator >= self.config.fixed_dt
            and steps < self.config.max_simulation_steps
        ):
            self._manager.simulation_step()
            self._accumulator -= self.config.fixed_dt
            steps += 1
        if steps == self.config.max_simulation_steps and self._accumulator >= self.config.fixed_dt:
            # Drop the excess backlog after the bounded recovery window.
            self._accumulator %= self.config.fixed_dt
        if self._renderer is not None:
            self._renderer.set_interpolation_alpha(self._accumulator / self.config.fixed_dt)
        if self._battle_renderer is not None:
            self._battle_renderer.set_interpolation_alpha(
                self._accumulator / self.config.fixed_dt
            )
        return steps

    def _apply_current_settings(self) -> None:
        if self._manager is None or self._renderer is None or self._audio is None:
            return
        self._renderer.set_catalog(self._manager.session.catalog)
        if self._battle_renderer is not None:
            self._battle_renderer.set_catalog(
                self._manager.battle_session.players[0].catalog
            )
        options = getattr(self._manager.current, "settings", None)
        if not isinstance(options, SettingsData) or options == self._applied_settings:
            return
        self._audio.set_gains(
            master=options.master_gain,
            effects=options.effects_gain,
            music=options.music_gain,
        )
        self._renderer.safe_area_fraction = options.safe_area_fraction
        self._renderer.set_reduced_effects(options.effects_reduced)
        if self._battle_renderer is not None:
            self._battle_renderer.safe_area_fraction = options.safe_area_fraction
            self._battle_renderer.set_reduced_effects(options.effects_reduced)
        if options.fullscreen != self._settings.fullscreen:
            self._settings = options
            self._create_display()
            self._renderer = Renderer(
                self._screen,
                safe_area_fraction=options.safe_area_fraction,
                reduced_effects=options.effects_reduced,
                debug_colliders=self.config.debug_colliders,
            )
            self._menu_canvas = _MenuCanvas(self._pygame, self._screen)
            self._battle_renderer = BattleRenderer(
                self._screen, safe_area_fraction=options.safe_area_fraction,
                reduced_effects=options.effects_reduced,
                debug_colliders=self.config.debug_colliders,
            )
            self._renderer.set_catalog(self._manager.session.catalog)
            self._battle_renderer.set_catalog(
                self._manager.battle_session.players[0].catalog
            )
        self._applied_settings = options

    def _draw(self) -> None:
        if self._manager is None:
            return
        if self._manager.current_name == "play":
            assert self._renderer is not None
            self._manager.current.draw(self._renderer)
        elif self._manager.current_name == "battle":
            assert self._battle_renderer is not None
            self._manager.current.draw(self._battle_renderer)
        else:
            assert self._menu_canvas is not None
            self._manager.current.draw(self._menu_canvas)
        if self._focus_lock:
            assert self._pygame is not None
            text = self._pygame.font.Font(None, 38).render(
                "Foco perdido · pressione confirmar para continuar",
                True,
                (24, 59, 78),
            )
            self._screen.blit(text, text.get_rect(center=(self._screen.get_width() // 2, 52)))
        elif self._battle_connection_lock and self._battle_controls is not None:
            assert self._pygame is not None
            message = (
                "Controles reconectados · confirme para continuar"
                if self._battle_controls.ready else
                f"Reconecte jogador {self._battle_controls.missing_players} · Voltar: menu"
            )
            text = self._pygame.font.Font(None, 34).render(message, True, (255, 247, 220))
            rect = text.get_rect(center=(self._screen.get_width() // 2, 26))
            self._pygame.draw.rect(self._screen, (20, 30, 48), rect.inflate(24, 12))
            self._screen.blit(text, rect)
        elif self._controller_reconnect_lock:
            assert self._pygame is not None
            connected = (
                self._registry is not None
                and self._registry.active_instance_id is not None
            )
            message = (
                "Controle removido · confirme no teclado para continuar (--desktop)"
                if self._input.active_backend is InputBackend.KEYBOARD_EMULATED else
                "Controle reconectado · pressione confirmar para continuar"
                if connected
                else "Controle removido · reconecte o controle do jogador 1"
            )
            text = self._pygame.font.Font(None, 34).render(
                message, True, (24, 59, 78)
            )
            self._screen.blit(
                text,
                text.get_rect(center=(self._screen.get_width() // 2, 52)),
            )

    @staticmethod
    def _controller_identity(device: Any | None) -> str | None:
        if device is None:
            return None
        guid = str(getattr(device, "guid", "")).strip().casefold()
        if guid:
            return f"guid:{guid}"
        name = str(getattr(device, "name", "")).strip().casefold()
        return f"name:{name}" if name else None

    def _update_battle_connection(self) -> None:
        assert self._battle_controls is not None
        assert self._registry is not None
        assert self._manager is not None
        # Keep menu ownership on player one, or the surviving pad while waiting.
        available = [slot for slot in self._battle_controls.slots if slot is not None]
        selected = available[0] if available else None
        if self._registry.active_instance_id != selected:
            self._registry.select(selected)
            self._input.register_adapter(InputBackend.NATIVE, self._registry)
            self._input.select_backend(InputBackend.NATIVE if selected is not None else None)
        if selected is not None:
            self._selected_controller_identity = self._controller_identity(
                self._registry.devices[selected]
            )
        if not self._battle_controls.ready and not self._battle_connection_lock:
            self._battle_connection_lock = True
            self._battle_resume_gameplay = self._manager.current_name == "battle"
            self._manager.battle_session.pause()
            self._audio.pause()
            self._accumulator = 0.0
            self._clear_input_states()
            self._manager.reset_input()


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry function used by both package and compatibility launchers."""
    parser = argparse.ArgumentParser(description="Suika Elika — clássico e batalha local")
    parser.add_argument(
        "--desktop", action="store_true",
        help="permitir teclado no clássico/menu quando nenhum controle estiver conectado",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="desenhar colisores e limites das frutas para análise visual",
    )
    parser.add_argument("--p1-index", type=int, help="índice Pygame do controle do jogador 1")
    parser.add_argument("--p2-index", type=int, help="índice Pygame do controle do jogador 2")
    args = parser.parse_args(argv)
    indexes = None
    if args.p1_index is not None or args.p2_index is not None:
        if args.p1_index is None or args.p2_index is None:
            parser.error("informe --p1-index e --p2-index juntos")
        if min(args.p1_index, args.p2_index) < 0 or args.p1_index == args.p2_index:
            parser.error("P1 e P2 precisam de índices distintos e não negativos")
        indexes = (args.p1_index, args.p2_index)
    return App(
        AppConfig(
            allow_keyboard_fallback=args.desktop,
            player_indexes=indexes,
            debug_colliders=args.debug,
        )
    ).run()


__all__ = ["App", "main"]
