"""Split-screen battle presentation on the shared logical TV viewport."""

from __future__ import annotations

from math import pi
from typing import Any

from suika_elika.contracts import SessionSnapshot, Vector2
from suika_elika.game.battle import BATTLE_HEIGHT, BATTLE_WIDTH, BattleSnapshot
from suika_elika.game.spawning import AimCircle, predict_aim
from suika_elika.rendering.assets import GameArt
from suika_elika.rendering.renderer import LAUNCH_Y, Renderer


class BattleRenderer(Renderer):
    def __init__(
        self,
        target: Any,
        *,
        safe_area_fraction: float = 0.05,
        reduced_effects: bool = False,
    ) -> None:
        super().__init__(
            target, safe_area_fraction=safe_area_fraction, reduced_effects=reduced_effects
        )
        self._battle_background = GameArt().background_surface((1280, 720), battle=True)
        self._battle_container = self.art.container_surface((int(BATTLE_WIDTH), int(BATTLE_HEIGHT)))
        self._score_panel = self._pygame.Surface((520, 114), self._pygame.SRCALPHA, 32)
        self._pygame.draw.rect(
            self._score_panel,
            (20, 30, 48, 218),
            (0, 0, 520, 114),
            border_radius=20,
        )

    def draw_battle(self, snapshot: BattleSnapshot) -> None:
        pygame = self._pygame
        self._logical.blit(self._battle_background, (0, 0))
        pygame.draw.line(self._logical, (255, 230, 172), (640, 40), (640, 660), 3)
        for index, player in enumerate(snapshot.players):
            self._draw_player(player, index, snapshot.target)
        label = self._font(24).render(
            "BATALHA 1x1 · Primeiro a 500 vence · Start: pausar",
            True,
            (255, 247, 220),
        )
        shadow = self._pygame.Surface((700, 36), self._pygame.SRCALPHA, 32)
        shadow.fill((20, 30, 48, 215))
        self._logical.blit(shadow, (290, 664))
        self._logical.blit(label, label.get_rect(center=(640, 682)))
        self._present()

    def _draw_player(self, snapshot: SessionSnapshot, index: int, target: int) -> None:
        pygame = self._pygame
        x, y = 80 + index * 640, 180
        color = (126, 219, 255) if index == 0 else (255, 185, 119)
        self._logical.blit(self._score_panel, (x - 20, 38))
        self._text(f"JOGADOR {index + 1}", (x, 48), 30, color)
        self._text(f"{snapshot.score} / {target}", (x, 78), 42, (255, 247, 220))
        self._text("PRÓXIMA", (x + 330, 52), 22, (255, 247, 220))
        bar = pygame.Rect(x, 124, 260, 12)
        pygame.draw.rect(self._logical, (65, 77, 90), bar, border_radius=6)
        fill = bar.copy()
        fill.width = round(bar.width * min(1, snapshot.score / target))
        pygame.draw.rect(self._logical, color, fill, border_radius=6)
        self._logical.blit(self._battle_container, (x, y))
        danger_color = (255, 90, 90) if snapshot.danger_progress else (228, 155, 132)
        for dx in range(8, int(BATTLE_WIDTH) - 8, 28):
            pygame.draw.line(
                self._logical,
                danger_color,
                (x + dx, y + 52),
                (x + min(dx + 14, int(BATTLE_WIDTH) - 8), y + 52),
                3,
            )
        current = snapshot.current_fruit
        if current is not None:
            circles = tuple(
                AimCircle(
                    f.entity_id,
                    f.current_pose.position,
                    self.catalog.get(f.fruit_id).definition.radius,
                )
                for f in snapshot.fruits
            )
            aim = predict_aim(
                snapshot.launcher_x,
                current.radius,
                circles,
                width=BATTLE_WIDTH,
                height=BATTLE_HEIGHT,
                launch_y=LAUNCH_Y,
            )
            for dy in range(round(LAUNCH_Y), round(aim.y), 15):
                pygame.draw.circle(self._logical, (255, 247, 220), (round(x + aim.x), y + dy), 2)
            self._draw_fruit(
                current,
                Vector2(x + snapshot.launcher_x, y + LAUNCH_Y),
                angle=0,
                world_coordinates=False,
            )
        if snapshot.next_fruit is not None:
            self._draw_fruit(
                snapshot.next_fruit,
                Vector2(x + 430, 104),
                angle=0,
                scale=0.52,
                world_coordinates=False,
            )
        old_clip = self._logical.get_clip()
        self._logical.set_clip((x, y - 72, int(BATTLE_WIDTH), int(BATTLE_HEIGHT) + 72))
        for fruit in snapshot.fruits:
            first, second = fruit.previous_pose, fruit.current_pose
            alpha = self.interpolation_alpha
            position = Vector2(
                x + first.position.x + (second.position.x - first.position.x) * alpha,
                y + first.position.y + (second.position.y - first.position.y) * alpha,
            )
            delta = (second.angle - first.angle + pi) % (2 * pi) - pi
            self._draw_fruit(
                self.catalog.get(fruit.fruit_id).definition,
                position,
                angle=first.angle + delta * alpha,
                danger=fruit.danger_seconds > 0,
                world_coordinates=False,
            )
        self._logical.set_clip(old_clip)
        pygame.draw.lines(
            self._logical, color, False, ((x, y), (x, y + 454), (x + 480, y + 454), (x + 480, y)), 5
        )
        if snapshot.danger_progress:
            self._text("PERIGO!", (x + 170, y + 64), 30, (255, 100, 100))

    def _text(
        self, text: str, position: tuple[int, int], size: int, color: tuple[int, int, int]
    ) -> None:
        self._logical.blit(self._font(size).render(text, True, color), position)
