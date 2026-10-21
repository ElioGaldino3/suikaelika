"""Pygame composition root and bounded fixed-step application loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from suika_elika.audio import create_audio_manager
from suika_elika.config import AppConfig
from suika_elika.contracts import InputAction, RoundState, SettingsData
from suika_elika.game.physics import PhysicsConfig, PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.input.controller import NativeInputRegistry
from suika_elika.input.manager import InputBackend, InputManager, InputSample
from suika_elika.persistence import JsonPersistence
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
            getattr(keys, "K_ESCAPE", -3): (InputAction.CANCEL,),
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
        surface.fill((112, 201, 235))
        title_font = self.pygame.font.Font(None, layout.title_font_size)
        body_font = self.pygame.font.Font(None, layout.body_font_size)
        small_font = self.pygame.font.Font(None, layout.footer_font_size)
        title = title_font.render(snapshot.title, True, (24, 59, 78))
        surface.blit(title, title.get_rect(center=(width // 2, layout.title_y)))

        for index, line in enumerate(snapshot.subtitle.splitlines()):
            rendered = small_font.render(line, True, (34, 73, 89))
            subtitle_y = layout.subtitle_y + index * layout.subtitle_spacing
            surface.blit(rendered, rendered.get_rect(center=(width // 2, subtitle_y)))

        for index, label in enumerate(snapshot.choices):
            selected = index == snapshot.selected_index
            color = (255, 247, 194) if selected else (24, 59, 78)
            text = body_font.render(("›  " if selected else "   ") + label, True, color)
            item_y = layout.choices_y + index * layout.choice_spacing
            surface.blit(text, text.get_rect(center=(width // 2, round(item_y))))

        footer_text = [line for line in (snapshot.message, snapshot.footer) if line]
        first_footer_y = layout.footer_y - (len(footer_text) - 1) * layout.footer_spacing
        for index, line in enumerate(footer_text):
            rendered = small_font.render(line, True, (24, 59, 78))
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
        self._input = InputManager()
        self._audio: Any = None
        self._persistence: Any = None
        self._session: GameSession | None = None
        self._manager: SceneManager | None = None
        self._screen: Any = None
        self._renderer: Renderer | None = None
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
        except Exception:
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
        self._create_display()

        self._registry = NativeInputRegistry(pygame)
        devices = self._registry.discover()
        if devices:
            self._registry.select(devices[0])
            self._input.register_adapter(InputBackend.NATIVE, self._registry)
            self._input.select_backend(InputBackend.NATIVE)
            controller_status = "Controle conectado"
        else:
            controller_status = "Controle não conectado"
            if self.config.allow_keyboard_fallback:
                self._keyboard = _KeyboardAdapter(pygame)
                self._input.register_adapter(InputBackend.KEYBOARD_EMULATED, self._keyboard)
                self._input.select_backend(InputBackend.KEYBOARD_EMULATED)
                controller_status += " · teclado de desenvolvimento"

        self._session = GameSession(
            PhysicsWorld(PhysicsConfig(fixed_dt=self.config.fixed_dt)),
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
        )
        self._menu_canvas = _MenuCanvas(pygame, self._screen)
        self._clock = pygame.time.Clock()
        self._manager = SceneManager(
            self._session,
            self._persistence,
            self._input,
            self._audio,
            controller_status=controller_status,
        )

    def _create_display(self) -> None:
        pygame = self._pygame
        assert pygame is not None
        flags = pygame.FULLSCREEN if self._settings.fullscreen else 0
        self._screen = pygame.display.set_mode(self.config.window_size, flags)
        pygame.display.set_caption("Suika Elika")

    def _process_events(self, events: tuple[Any, ...]) -> None:
        if self._registry is not None:
            self._registry.process_events(events)
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
        if self._keyboard is not None:
            self._keyboard.clear()
        if self._registry is not None:
            for adapter in self._registry.devices.values():
                reset = getattr(adapter, "reset_edges", None)
                if callable(reset):
                    reset()

    def _poll_and_dispatch(self, ui_delta: float, events: tuple[Any, ...]) -> None:
        del events
        assert self._manager is not None
        managed = self._input.poll(ui_delta)
        self._manager.handle_actions(managed.frame)

    def _poll_focus_confirmation(self, ui_delta: float, events: tuple[Any, ...]) -> None:
        del events
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
        if self._manager is None or self._manager.current_name != "play":
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
        return steps

    def _apply_current_settings(self) -> None:
        if self._manager is None or self._renderer is None or self._audio is None:
            return
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
        if options.fullscreen != self._settings.fullscreen:
            self._settings = options
            self._create_display()
            self._renderer = Renderer(
                self._screen,
                safe_area_fraction=options.safe_area_fraction,
                reduced_effects=options.effects_reduced,
            )
            self._menu_canvas = _MenuCanvas(self._pygame, self._screen)
        self._applied_settings = options

    def _draw(self) -> None:
        if self._manager is None:
            return
        if self._manager.current_name == "play":
            assert self._renderer is not None
            self._manager.current.draw(self._renderer)
        else:
            assert self._menu_canvas is not None
            self._manager.current.draw(self._menu_canvas)
        if (
            self._focus_lock
            and self._session is not None
            and self._session.round_state is RoundState.PAUSED
        ):
            assert self._pygame is not None
            text = self._pygame.font.Font(None, 38).render(
                "Foco perdido · pressione confirmar para continuar",
                True,
                (24, 59, 78),
            )
            self._screen.blit(text, text.get_rect(center=(self.config.window_size[0] // 2, 52)))


def main() -> int:
    """Console entry function used by both package and compatibility launchers."""
    return App().run()


__all__ = ["App", "main"]
