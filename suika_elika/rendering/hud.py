"""Small, high-contrast HUD drawing helpers for the logical 1280×720 canvas."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from suika_elika.contracts import SessionSnapshot
from suika_elika.game.catalog import FruitCatalog

Surface = Any

INK = (24, 59, 78)
PANEL = (244, 251, 247)
ACCENT = (249, 201, 71)
DANGER = (228, 85, 85)
MUTED = (76, 110, 124)


@dataclass(frozen=True, slots=True)
class HudMetrics:
    """Round values not present in the deliberately small render snapshot."""

    best_fruit_level: int = 0
    watermelons: int = 0
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (self.best_fruit_level, self.watermelons)
        ):
            raise ValueError("HUD counters must be non-negative integers")
        if not isfinite(self.duration_seconds) or self.duration_seconds < 0:
            raise ValueError("HUD duration must be finite and non-negative")


def draw_hud(
    pygame: Any,
    surface: Surface,
    snapshot: SessionSnapshot,
    catalog: FruitCatalog,
    metrics: HudMetrics,
    font: Any,
    small_font: Any,
) -> None:
    """Draw score, danger, progression, launch previews, and controller hints."""
    pygame.draw.rect(surface, PANEL, (64, 110, 276, 458), border_radius=22)
    pygame.draw.rect(surface, (185, 216, 211), (64, 110, 276, 458), 3, border_radius=22)

    _label_value(pygame, surface, font, small_font, "PONTOS", str(snapshot.score), 88, 140)
    _label_value(pygame, surface, font, small_font, "RECORDE", str(snapshot.high_score), 88, 220)
    best = catalog.entries[metrics.best_fruit_level - 1].name if metrics.best_fruit_level else "—"
    _label_value(pygame, surface, font, small_font, "MELHOR FRUTA", best, 88, 300)
    _label_value(pygame, surface, font, small_font, "MELANCIAS", str(metrics.watermelons), 88, 380)

    danger_label = "PERIGO" if snapshot.danger_progress > 0 else "PILHA SEGURA"
    danger_color = DANGER if snapshot.danger_progress > 0 else MUTED
    text = small_font.render(danger_label, True, danger_color)
    surface.blit(text, (88, 455))
    bar = pygame.Rect(88, 487, 226, 20)
    pygame.draw.rect(surface, (216, 230, 226), bar, border_radius=10)
    if snapshot.danger_progress > 0:
        fill = bar.copy()
        fill.width = max(1, round(bar.width * snapshot.danger_progress))
        pygame.draw.rect(surface, DANGER, fill, border_radius=10)
    pygame.draw.rect(surface, INK, bar, 2, border_radius=10)

    if snapshot.current_fruit is not None:
        current = small_font.render("ATUAL", True, INK)
        surface.blit(current, (930, 56))
        current_name = small_font.render(
            catalog.get(snapshot.current_fruit.fruit_id).name, True, INK
        )
        surface.blit(current_name, (930, 82))
    if snapshot.next_fruit is not None:
        upcoming = small_font.render("PRÓXIMA", True, INK)
        surface.blit(upcoming, (1084, 56))
        next_name = small_font.render(
            catalog.get(snapshot.next_fruit.fruit_id).name, True, INK
        )
        surface.blit(next_name, (1084, 82))

    _draw_progression(pygame, surface, catalog, metrics.best_fruit_level)
    elapsed = max(0, int(metrics.duration_seconds))
    time_text = small_font.render(f"{elapsed // 60:02d}:{elapsed % 60:02d}", True, INK)
    surface.blit(time_text, (88, 525))
    hint = small_font.render("MOVER  ·  SOLTAR  ·  AJUSTE FINO  ·  PAUSA", True, INK)
    surface.blit(hint, hint.get_rect(center=(780, 672)))


def _label_value(
    pygame: Any,
    surface: Surface,
    value_font: Any,
    label_font: Any,
    label: str,
    value: str,
    x: int,
    y: int,
) -> None:
    surface.blit(label_font.render(label, True, MUTED), (x, y))
    rendered = value_font.render(value, True, INK)
    surface.blit(rendered, (x, y + 24))


def _draw_progression(
    pygame: Any, surface: Surface, catalog: FruitCatalog, best_level: int
) -> None:
    """Render compact level markers without shrinking the main HUD text."""
    entries = catalog.entries
    left, y, usable = 382, 650, 798
    gap = usable / max(1, len(entries) - 1)
    for index, entry in enumerate(entries):
        x = round(left + index * gap)
        selected = entry.level <= best_level
        color = ACCENT if selected else (213, 230, 224)
        pygame.draw.circle(surface, INK, (x, y), 13)
        pygame.draw.circle(surface, color, (x, y), 10)
        if index < len(entries) - 1:
            next_x = round(left + (index + 1) * gap)
            pygame.draw.line(
                surface,
                (135, 179, 167),
                (x + 14, y),
                (next_x - 14, y),
                3,
            )


__all__ = ["HudMetrics", "draw_hud"]
