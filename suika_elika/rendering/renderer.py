"""Pygame drawing adapter for session snapshots and copied domain events."""

from __future__ import annotations

from importlib import import_module
from math import degrees, isfinite, pi, sin
from typing import Any

from suika_elika.contracts import DomainEvent, FruitDefinition, SessionSnapshot, Vector2
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.game.spawning import AimCircle, predict_aim
from suika_elika.rendering.effects import EffectSystem
from suika_elika.rendering.hud import HudMetrics, draw_hud
from suika_elika.rendering.procedural import ProceduralArt
from suika_elika.rendering.viewport import LOGICAL_HEIGHT, LOGICAL_WIDTH, Viewport

Surface = Any
WORLD_ORIGIN = Vector2(380.0, 164.0)
WORLD_WIDTH = 800.0
WORLD_HEIGHT = 460.0
LAUNCH_Y = -18.0
BACKGROUND = (112, 201, 235)
INK = (24, 59, 78)
DANGER = (228, 85, 85)
CONTAINER_INNER = (232, 247, 243)


class Renderer:
    """Render one immutable game snapshot into any Pygame display surface.

    The caller owns display creation and presentation. This adapter composes a
    logical 1280×720 canvas, then uniformly scales it into the target surface.
    """

    def __init__(
        self,
        target: Surface,
        *,
        catalog: FruitCatalog | None = None,
        art: ProceduralArt | None = None,
        safe_area_fraction: float = 0.05,
        effect_seed: int = 0,
        reduced_effects: bool = False,
    ) -> None:
        try:
            self._pygame = import_module("pygame")
        except ImportError as error:
            raise RuntimeError("Pygame is required to construct the renderer") from error
        if type(reduced_effects) is not bool:
            raise TypeError("reduced_effects must be a boolean")
        self.target = target
        self.catalog = catalog or load_catalog()
        self.art = art or ProceduralArt()
        self.reduced_effects = reduced_effects
        self._logical = self._pygame.Surface(
            (int(LOGICAL_WIDTH), int(LOGICAL_HEIGHT)), self._pygame.SRCALPHA, 32
        )
        if not self._pygame.font.get_init():
            self._pygame.font.init()
        self._fonts: dict[int, Any] = {}
        self._fruit_surfaces = self.art.fruit_surfaces(self.catalog)
        self._small_fruit_surfaces: dict[str, Surface] = {}
        self._background = self.art.background_surface(
            (int(LOGICAL_WIDTH), int(LOGICAL_HEIGHT))
        )
        self._container = self.art.container_surface(
            (int(WORLD_WIDTH), int(WORLD_HEIGHT))
        )
        self.effects = EffectSystem(seed=effect_seed)
        self.metrics = HudMetrics()
        self.interpolation_alpha = 1.0
        self.presentation_time = 0.0
        self.safe_area_fraction = safe_area_fraction
        self._presentation_rect = (0, 0, 0, 0)
        target_width, target_height = self.target.get_size()
        Viewport(
            target_width,
            target_height,
            safe_area_fraction=self.safe_area_fraction,
        )

    def set_reduced_effects(self, enabled: bool) -> None:
        """Apply the persisted accessibility preference to future effects."""
        if type(enabled) is not bool:
            raise TypeError("reduced effects flag must be a boolean")
        self.reduced_effects = enabled

    @property
    def presentation_rect(self) -> tuple[int, int, int, int]:
        """Physical bounds used for the logical canvas on the last draw."""
        return self._presentation_rect

    def set_round_metrics(
        self,
        *,
        best_fruit_level: int,
        watermelons: int,
        duration_seconds: float,
    ) -> None:
        """Supply immutable round counters omitted from SessionSnapshot."""
        self.metrics = HudMetrics(best_fruit_level, watermelons, duration_seconds)

    def set_interpolation_alpha(self, value: float) -> None:
        """Set the fraction between the session's previous/current poses."""
        if not isfinite(value) or not 0 <= value <= 1:
            raise ValueError("interpolation alpha must be finite and between 0 and 1")
        self.interpolation_alpha = value

    def advance_presentation(
        self, delta_seconds: float, events: tuple[DomainEvent, ...] = ()
    ) -> None:
        """Advance visual clocks; this method never mutates gameplay state."""
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("presentation delta must be finite and non-negative")
        self.presentation_time += delta_seconds
        self.effects.update(
            delta_seconds,
            events,
            reduced=self.reduced_effects,
        )

    def draw_session(
        self, snapshot: SessionSnapshot, events: tuple[DomainEvent, ...]
    ) -> None:
        """Implement CanvasPort.draw_session without exposing Pygame to gameplay."""
        self.effects.update(0.0, events, reduced=self.reduced_effects)
        self._logical.blit(self._background, (0, 0))
        self._draw_world_backdrop()
        self._draw_aim(snapshot)
        self._draw_launcher(snapshot)
        self._draw_fruits(snapshot)
        self._draw_effects()
        self._draw_container_front()
        self._draw_hud(snapshot)
        if snapshot.round_state.value in {"paused", "game_over"}:
            self._draw_state_overlay(snapshot.round_state.value)
        self._present()

    def _draw_world_backdrop(self) -> None:
        pygame = self._pygame
        x, y = round(WORLD_ORIGIN.x), round(WORLD_ORIGIN.y)
        pygame.draw.rect(
            self._logical,
            CONTAINER_INNER,
            (x, y, int(WORLD_WIDTH), int(WORLD_HEIGHT)),
            border_radius=6,
        )
        self._logical.blit(self._container, (x, y))
        danger_y = round(y + 52)
        dash = 16
        for start in range(x + 8, x + int(WORLD_WIDTH) - 8, dash * 2):
            end = min(start + dash, x + int(WORLD_WIDTH) - 8)
            self._pygame.draw.line(
                self._logical,
                (*DANGER, 210),
                (start, danger_y),
                (end, danger_y),
                3,
            )

    def _draw_aim(self, snapshot: SessionSnapshot) -> None:
        current = snapshot.current_fruit
        if current is None:
            return
        circles = tuple(
            AimCircle(
                fruit.entity_id,
                Vector2(
                    fruit.current_pose.position.x,
                    fruit.current_pose.position.y,
                ),
                self.catalog.get(fruit.fruit_id).definition.radius,
            )
            for fruit in snapshot.fruits
        )
        prediction = predict_aim(
            snapshot.launcher_x,
            current.radius,
            circles,
            width=WORLD_WIDTH,
            height=WORLD_HEIGHT,
            launch_y=LAUNCH_Y,
        )
        x = round(WORLD_ORIGIN.x + prediction.x)
        start_y = round(WORLD_ORIGIN.y + LAUNCH_Y)
        end_y = round(WORLD_ORIGIN.y + prediction.y)
        color = (255, 255, 244)
        for y in range(start_y, max(start_y + 1, end_y), 15):
            self._pygame.draw.circle(self._logical, color, (x, y), 3)

    def _draw_launcher(self, snapshot: SessionSnapshot) -> None:
        definition = snapshot.current_fruit
        if definition is None:
            return
        wobble = 1.5 * sin(self.presentation_time * 3.2)
        self._draw_fruit(
            definition,
            Vector2(snapshot.launcher_x, LAUNCH_Y + wobble),
            angle=0.0,
            scale=1.0,
        )
        next_fruit = snapshot.next_fruit
        if next_fruit is not None:
            self._draw_fruit(
                next_fruit,
                Vector2(1105.0, 112.0),
                angle=0.0,
                scale=0.52,
                world_coordinates=False,
            )

    def _draw_fruits(self, snapshot: SessionSnapshot) -> None:
        alpha = self.interpolation_alpha
        clip = self._pygame.Rect(round(WORLD_ORIGIN.x), 0, int(WORLD_WIDTH), int(LOGICAL_HEIGHT))
        previous_clip = self._logical.get_clip()
        self._logical.set_clip(clip)
        try:
            for fruit in snapshot.fruits:
                first = fruit.previous_pose
                second = fruit.current_pose
                position = Vector2(
                    first.position.x + (second.position.x - first.position.x) * alpha,
                    first.position.y + (second.position.y - first.position.y) * alpha,
                )
                angle_delta = (
                    (second.angle - first.angle + pi) % (2 * pi) - pi
                )
                angle = first.angle + angle_delta * alpha
                self._draw_fruit(
                    self.catalog.get(fruit.fruit_id).definition,
                    position,
                    angle=angle,
                    danger=fruit.danger_eligible and fruit.danger_seconds > 0,
                )
        finally:
            self._logical.set_clip(previous_clip)

    def _draw_fruit(
        self,
        definition: FruitDefinition,
        position: Vector2,
        *,
        angle: float,
        scale: float = 1.0,
        danger: bool = False,
        world_coordinates: bool = True,
    ) -> None:
        pygame = self._pygame
        sprite = self._fruit_surfaces[definition.visual_key]
        if scale != 1.0:
            size = (
                max(1, round(sprite.get_width() * scale)),
                max(1, round(sprite.get_height() * scale)),
            )
            if scale == 0.52:
                sprite = self._small_fruit_surfaces.get(definition.visual_key)
                if sprite is None:
                    sprite = pygame.transform.smoothscale(
                        self._fruit_surfaces[definition.visual_key], size
                    )
                    self._small_fruit_surfaces[definition.visual_key] = sprite
            else:
                sprite = pygame.transform.smoothscale(sprite, size)
        if angle:
            # Pygame rotates counter-clockwise; the Y-down game view flips that sign.
            sprite = pygame.transform.rotate(sprite, -degrees(angle))
        px = position.x + (WORLD_ORIGIN.x if world_coordinates else 0.0)
        py = position.y + (WORLD_ORIGIN.y if world_coordinates else 0.0)
        rect = sprite.get_rect(center=(round(px), round(py)))
        if danger:
            pulse = 0.5 + 0.5 * sin(self.presentation_time * 7)
            pygame.draw.circle(
                self._logical,
                (255, round(90 + 95 * pulse), 90),
                (round(px), round(py)),
                round(definition.radius + 6),
                max(2, round(2 + pulse * 2)),
            )
        self._logical.blit(sprite, rect)

    def _draw_effects(self) -> None:
        pygame = self._pygame
        for flash in self.effects.flashes:
            fraction = max(0.0, 1.0 - flash.age / flash.lifetime)
            center = (
                round(WORLD_ORIGIN.x + flash.position.x),
                round(WORLD_ORIGIN.y + flash.position.y),
            )
            radius = round(8 + (1.0 - fraction) * 24)
            pygame.draw.circle(self._logical, (255, 236, 158), center, radius, 3)
        for particle in self.effects.particles:
            fraction = max(0.0, 1.0 - particle.age / particle.lifetime)
            center = (
                round(WORLD_ORIGIN.x + particle.position.x),
                round(WORLD_ORIGIN.y + particle.position.y),
            )
            pygame.draw.circle(
                self._logical,
                particle.color,
                center,
                max(1, round(particle.radius * fraction)),
            )

    def _draw_container_front(self) -> None:
        pygame = self._pygame
        left = round(WORLD_ORIGIN.x)
        right = round(WORLD_ORIGIN.x + WORLD_WIDTH)
        bottom = round(WORLD_ORIGIN.y + WORLD_HEIGHT)
        rim = (23, 105, 133)
        pygame.draw.line(
            self._logical, rim, (left, bottom - 4), (left + 160, bottom - 4), 7
        )
        pygame.draw.line(
            self._logical,
            rim,
            (left + 160, bottom - 4),
            (right - 160, bottom - 4),
            7,
        )
        pygame.draw.line(
            self._logical, rim, (right - 160, bottom - 4), (right, bottom - 4), 7
        )
        pygame.draw.line(self._logical, rim, (left, round(WORLD_ORIGIN.y)), (left, bottom), 7)
        pygame.draw.line(self._logical, rim, (right, round(WORLD_ORIGIN.y)), (right, bottom), 7)

    def _draw_hud(self, snapshot: SessionSnapshot) -> None:
        draw_hud(
            self._pygame,
            self._logical,
            snapshot,
            self.catalog,
            self.metrics,
            self._font(42),
            self._font(22),
        )

    def _draw_state_overlay(self, state: str) -> None:
        pygame = self._pygame
        veil = pygame.Surface((int(LOGICAL_WIDTH), int(LOGICAL_HEIGHT)), pygame.SRCALPHA, 32)
        veil.fill((24, 59, 78, 132))
        self._logical.blit(veil, (0, 0))
        message = "PAUSADO" if state == "paused" else "FIM DE JOGO"
        label = self._font(54).render(message, True, (255, 247, 220))
        self._logical.blit(label, label.get_rect(center=(640, 360)))

    def _present(self) -> None:
        pygame = self._pygame
        target_width, target_height = self.target.get_size()
        viewport = Viewport(
            target_width,
            target_height,
            safe_area_fraction=self.safe_area_fraction,
        )
        safe_rect = viewport.safe_rect
        target_rect = pygame.Rect(
            round(safe_rect.x),
            round(safe_rect.y),
            max(1, round(safe_rect.width)),
            max(1, round(safe_rect.height)),
        )
        self._presentation_rect = tuple(target_rect)
        self.target.fill(BACKGROUND)
        if target_rect.size == self._logical.get_size():
            scaled = self._logical
        else:
            scaled = pygame.transform.smoothscale(self._logical, target_rect.size)
        self.target.blit(scaled, target_rect)

    def _font(self, size: int) -> Any:
        font = self._fonts.get(size)
        if font is None:
            font = self._pygame.font.Font(None, size)
            font.set_bold(True)
            self._fonts[size] = font
        return font


__all__ = ["Renderer"]
