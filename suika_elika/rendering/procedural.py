"""Cached, code-drawn art for the first image-free prototype.

Importing this module does not import Pygame or initialize SDL. Construct
``ProceduralArt`` after the application has selected a rendering backend.
Returned surfaces are cached and should be treated as read-only assets.
"""

from __future__ import annotations

from importlib import import_module
from math import ceil, pi
from typing import Any

from suika_elika.container_geometry import bowl_edge, bowl_outline_points
from suika_elika.game.catalog import FruitCatalog, FruitCatalogEntry

Color = tuple[int, int, int]
Surface = Any

OUTLINE: Color = (71, 47, 65)
CREAM: Color = (255, 247, 220)
LEAF: Color = (76, 145, 73)


def _color(value: str) -> Color:
    """Parse a catalog #RRGGBB color without depending on Pygame at import."""
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("fruit color must use #RRGGBB notation")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    except ValueError as error:
        raise ValueError("fruit color must use #RRGGBB notation") from error


def _shade(color: Color, factor: float) -> Color:
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)  # type: ignore[return-value]


class ProceduralArt:
    """Create and cache reusable fruit, container, and scenery surfaces."""

    __slots__ = ("_pygame", "_fruit_cache", "_container_cache", "_background_cache")

    def __init__(self) -> None:
        try:
            self._pygame = import_module("pygame")
        except ImportError as error:
            raise RuntimeError("Pygame is required to build procedural surfaces") from error
        self._fruit_cache: dict[tuple[str, float, str], Surface] = {}
        self._container_cache: dict[tuple[int, int], Surface] = {}
        self._background_cache: dict[tuple[int, int], Surface] = {}

    def fruit_surface(self, entry: FruitCatalogEntry) -> Surface:
        """Return a cached, centered sprite whose body fits its physics radius."""
        key = (entry.fruit_id, entry.definition.radius, entry.color)
        cached = self._fruit_cache.get(key)
        if cached is not None:
            return cached

        pygame = self._pygame
        scale = 3
        radius = max(12, round(entry.definition.radius))
        margin = max(7, ceil(radius * 0.28))
        side = (radius + margin) * 2 * scale + 2
        high_res = pygame.Surface((side, side), pygame.SRCALPHA, 32)
        center = (side // 2, side // 2)
        scaled_radius = radius * scale
        base_color = _color(entry.color)
        self._draw_fruit(pygame, high_res, center, scaled_radius, entry.fruit_id, base_color)
        output_side = (radius + margin) * 2
        surface = pygame.transform.smoothscale(high_res, (output_side, output_side))
        self._fruit_cache[key] = surface
        return surface

    def fruit_surfaces(self, catalog: FruitCatalog) -> dict[str, Surface]:
        """Build all catalog sprites once, keyed by stable fruit ID."""
        return {entry.fruit_id: self.fruit_surface(entry) for entry in catalog.entries}

    def container_surface(self, size: tuple[int, int] = (800, 460)) -> Surface:
        """Return a transparent bowl overlay sized for the logical playfield."""
        self._validate_size(size)
        width, height = size
        cached = self._container_cache.get(size)
        if cached is not None:
            return cached

        pygame = self._pygame
        surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        edge = bowl_edge(width, height)
        rim = (62, 137, 191)
        inner = (192, 231, 241, 110)
        points = [
            tuple(round(value) for value in point)
            for point in bowl_outline_points(width, height, edge)
        ]
        pygame.draw.polygon(surface, inner, points)
        pygame.draw.line(surface, rim, points[0], points[-1], edge)
        pygame.draw.line(surface, rim, points[1], points[2], edge)
        pygame.draw.line(surface, rim, points[2], points[3], edge)
        pygame.draw.line(surface, rim, points[3], points[4], edge)
        pygame.draw.line(surface, rim, points[4], points[5], edge)
        pygame.draw.arc(
            surface,
            (124, 190, 220),
            (edge, -edge, width - 2 * edge, edge * 5),
            0.08,
            pi - 0.08,
            max(2, edge // 2),
        )
        self._container_cache[size] = surface
        return surface

    def background_surface(self, size: tuple[int, int] = (1280, 720)) -> Surface:
        """Return cached orchard scenery that stays quiet behind gameplay."""
        self._validate_size(size)
        width, height = size
        cached = self._background_cache.get(size)
        if cached is not None:
            return cached

        pygame = self._pygame
        surface = pygame.Surface(size, 0, 32)
        sky_top = (156, 224, 247)
        sky_bottom = (232, 246, 218)
        band_height = max(1, height // 90)
        for top in range(0, height, band_height):
            amount = top / max(1, height - 1)
            color = tuple(
                round(first + (second - first) * amount)
                for first, second in zip(sky_top, sky_bottom, strict=True)
            )
            pygame.draw.rect(surface, color, (0, top, width, band_height + 1))

        sun_center = (round(width * 0.82), round(height * 0.18))
        pygame.draw.circle(surface, (255, 236, 158), sun_center, round(height * 0.065))
        self._draw_cloud(pygame, surface, round(width * 0.2), round(height * 0.2), height * 0.06)
        self._draw_cloud(pygame, surface, round(width * 0.61), round(height * 0.29), height * 0.045)

        pygame.draw.polygon(
            surface,
            (130, 195, 157),
            [
                (0, round(height * 0.64)),
                (round(width * 0.18), round(height * 0.44)),
                (round(width * 0.36), round(height * 0.65)),
                (round(width * 0.55), round(height * 0.47)),
                (round(width * 0.79), round(height * 0.66)),
                (width, round(height * 0.48)),
                (width, height),
                (0, height),
            ],
        )
        pygame.draw.polygon(
            surface,
            (95, 165, 115),
            [
                (0, round(height * 0.76)),
                (round(width * 0.25), round(height * 0.61)),
                (round(width * 0.48), round(height * 0.77)),
                (round(width * 0.73), round(height * 0.60)),
                (width, round(height * 0.74)),
                (width, height),
                (0, height),
            ],
        )
        self._draw_plant(pygame, surface, round(width * 0.08), round(height * 0.84), height * 0.1)
        self._draw_plant(pygame, surface, round(width * 0.9), round(height * 0.88), height * 0.12)
        self._background_cache[size] = surface
        return surface

    @staticmethod
    def _validate_size(size: tuple[int, int]) -> None:
        if len(size) != 2 or any(type(value) is not int or value <= 0 for value in size):
            raise ValueError("surface size must contain two positive integers")

    @staticmethod
    def _draw_cloud(pygame: Any, surface: Surface, x: int, y: int, radius: float) -> None:
        r = max(2, round(radius))
        white = (255, 255, 244)
        pygame.draw.ellipse(surface, white, (x - 2 * r, y, 4 * r, r * 2))
        pygame.draw.circle(surface, white, (x - r, y), r)
        pygame.draw.circle(surface, white, (x + r // 2, y - r // 4), round(r * 1.25))
        pygame.draw.circle(surface, white, (x + 2 * r, y + r // 4), round(r * 0.8))

    @staticmethod
    def _draw_plant(pygame: Any, surface: Surface, x: int, y: int, height: float) -> None:
        h = max(3, round(height))
        pygame.draw.line(surface, (72, 123, 68), (x, y), (x, y - h), max(2, h // 10))
        pygame.draw.ellipse(surface, (111, 174, 94), (x - h, y - h * 3 // 4, h, h // 2))
        pygame.draw.ellipse(surface, (129, 187, 105), (x, y - h, h, h // 2))

    @classmethod
    def _draw_fruit(
        cls,
        pygame: Any,
        surface: Surface,
        center: tuple[int, int],
        radius: int,
        fruit_id: str,
        color: Color,
    ) -> None:
        x, y = center
        outline_width = max(2, round(radius * 0.075))
        # Draw the dark shape first, then a slightly inset fill.  Drawing a
        # stroked polygon/circle and filling the same geometry would cover its
        # outline on several Pygame primitives.
        cls._draw_silhouette(pygame, surface, center, radius, fruit_id, OUTLINE)
        cls._draw_silhouette(pygame, surface, center, radius - outline_width, fruit_id, color)

        # Keep details opaque on the SRCALPHA surface to avoid transparent holes.
        pygame.draw.ellipse(
            surface,
            _shade(color, 0.78),
            (
                x - round(radius * 0.29),
                y + round(radius * 0.31),
                round(radius * 0.58),
                round(radius * 0.14),
            ),
        )
        pygame.draw.ellipse(
            surface,
            (255, 255, 245),
            (
                x - round(radius * 0.32),
                y - round(radius * 0.47),
                round(radius * 0.54),
                round(radius * 0.16),
            ),
        )
        cls._draw_species(pygame, surface, center, radius, fruit_id, color)
        cls._draw_face(pygame, surface, center, radius)

    @staticmethod
    def _draw_silhouette(
        pygame: Any,
        surface: Surface,
        center: tuple[int, int],
        radius: int,
        fruit_id: str,
        color: Color,
    ) -> None:
        x, y = center
        r = radius
        if fruit_id == "lemon":
            points = [
                (x - r, y),
                (x - round(r * 0.7), y - round(r * 0.58)),
                (x + round(r * 0.65), y - round(r * 0.52)),
                (x + r, y),
                (x + round(r * 0.65), y + round(r * 0.52)),
                (x - round(r * 0.7), y + round(r * 0.58)),
            ]
            pygame.draw.polygon(surface, color, points)
        elif fruit_id == "pear":
            points = [
                (x, y - r),
                (x + round(r * 0.48), y - round(r * 0.42)),
                (x + round(r * 0.62), y + round(r * 0.25)),
                (x + round(r * 0.42), y + round(r * 0.82)),
                (x, y + r),
                (x - round(r * 0.42), y + round(r * 0.82)),
                (x - round(r * 0.62), y + round(r * 0.25)),
                (x - round(r * 0.48), y - round(r * 0.42)),
            ]
            pygame.draw.polygon(surface, color, points)
        elif fruit_id == "strawberry":
            points = [
                (x - round(r * 0.8), y - round(r * 0.55)),
                (x - round(r * 0.46), y - round(r * 0.74)),
                (x - round(r * 0.12), y - round(r * 0.62)),
                (x + round(r * 0.2), y - round(r * 0.72)),
                (x + round(r * 0.78), y - round(r * 0.5)),
                (x + round(r * 0.58), y + round(r * 0.3)),
                (x, y + r),
                (x - round(r * 0.58), y + round(r * 0.3)),
            ]
            pygame.draw.polygon(surface, color, points)
        elif fruit_id == "pineapple":
            points = [
                (x, y - r),
                (x + round(r * 0.76), y - round(r * 0.64)),
                (x + r, y - round(r * 0.1)),
                (x + round(r * 0.76), y + round(r * 0.64)),
                (x, y + r),
                (x - round(r * 0.76), y + round(r * 0.64)),
                (x - r, y - round(r * 0.1)),
                (x - round(r * 0.76), y - round(r * 0.64)),
            ]
            pygame.draw.polygon(surface, color, points)
        elif fruit_id == "peach":
            pygame.draw.circle(surface, color, (x, y), r)
            pygame.draw.ellipse(surface, color, (x - r, y - round(r * 0.52), r * 2, round(r * 1.5)))
        else:
            pygame.draw.circle(surface, color, (x, y), r)

    @staticmethod
    def _draw_species(
        pygame: Any,
        surface: Surface,
        center: tuple[int, int],
        radius: int,
        fruit_id: str,
        color: Color,
    ) -> None:
        x, y = center
        r = radius
        if fruit_id in {"cherry", "apple", "pear", "peach"}:
            pygame.draw.line(
                surface,
                OUTLINE,
                (x, y - r + 2),
                (x + round(r * 0.08), y - round(r * 1.18)),
                max(2, r // 12),
            )
            pygame.draw.line(
                surface,
                (117, 79, 51),
                (x, y - r + 2),
                (x + round(r * 0.08), y - round(r * 1.18)),
                max(1, r // 18),
            )
            pygame.draw.ellipse(
                surface,
                OUTLINE,
                (x + round(r * 0.05), y - round(r * 1.12), round(r * 0.65), round(r * 0.35)),
            )
            pygame.draw.ellipse(
                surface,
                LEAF,
                (x + round(r * 0.07), y - round(r * 1.1), round(r * 0.58), round(r * 0.26)),
            )
            if fruit_id == "peach":
                pygame.draw.arc(
                    surface,
                    _shade(color, 0.7),
                    (x - r // 2, y - r // 2, r, r),
                    -pi / 2,
                    pi / 2,
                    max(1, r // 16),
                )
        elif fruit_id == "grape":
            grape_color = _shade(color, 0.78)
            for dx, dy in (
                (0, -0.36),
                (-0.36, -0.1),
                (0.36, -0.1),
                (-0.52, 0.22),
                (-0.17, 0.28),
                (0.22, 0.28),
                (0.52, 0.22),
            ):
                grape_center = (x + round(r * dx), y + round(r * dy))
                grape_radius = max(2, round(r * 0.25))
                pygame.draw.circle(surface, OUTLINE, grape_center, grape_radius + max(1, r // 24))
                pygame.draw.circle(surface, grape_color, grape_center, grape_radius)
            pygame.draw.ellipse(
                surface,
                LEAF,
                (x - round(r * 0.14), y - round(r * 0.75), round(r * 0.42), round(r * 0.22)),
            )
        elif fruit_id == "orange":
            for dx, dy in (
                (-0.48, -0.28),
                (-0.2, -0.54),
                (0.2, -0.5),
                (0.5, -0.2),
                (-0.54, 0.12),
                (-0.27, 0.48),
                (0.25, 0.45),
                (0.53, 0.18),
            ):
                pygame.draw.circle(
                    surface,
                    _shade(color, 0.72),
                    (x + round(r * dx), y + round(r * dy)),
                    max(1, r // 22),
                )
        elif fruit_id == "strawberry":
            crown = [
                (x - round(r * 0.78), y - round(r * 0.54)),
                (x - round(r * 0.52), y - round(r * 0.78)),
                (x - round(r * 0.2), y - round(r * 0.68)),
                (x, y - round(r * 0.84)),
                (x + round(r * 0.2), y - round(r * 0.68)),
                (x + round(r * 0.52), y - round(r * 0.78)),
                (x + round(r * 0.78), y - round(r * 0.5)),
                (x + round(r * 0.38), y - round(r * 0.54)),
                (x, y - round(r * 0.59)),
                (x - round(r * 0.38), y - round(r * 0.54)),
            ]
            pygame.draw.polygon(surface, OUTLINE, crown)
            pygame.draw.polygon(
                surface,
                LEAF,
                [(x + round((px - x) * 0.94), y + round((py - y) * 0.94)) for px, py in crown],
            )
            for dx, dy in (
                (-0.42, -0.2),
                (-0.12, -0.3),
                (0.2, -0.2),
                (0.44, -0.08),
                (-0.34, 0.18),
                (0.02, 0.08),
                (0.35, 0.24),
                (-0.15, 0.48),
                (0.17, 0.47),
            ):
                px, py = x + round(r * dx), y + round(r * dy)
                pygame.draw.ellipse(
                    surface,
                    CREAM,
                    (px - max(1, r // 24), py - max(2, r // 14), max(2, r // 12), max(4, r // 6)),
                )
        elif fruit_id == "pineapple":
            for offset in (-0.55, -0.27, 0, 0.27, 0.55):
                pygame.draw.line(
                    surface,
                    _shade(color, 0.66),
                    (x + round(r * offset), y - round(r * 0.78)),
                    (x + round(r * (offset - 0.32)), y + round(r * 0.78)),
                    max(1, r // 18),
                )
                pygame.draw.line(
                    surface,
                    _shade(color, 0.66),
                    (x + round(r * (offset - 0.32)), y - round(r * 0.6)),
                    (x + round(r * offset), y + round(r * 0.62)),
                    max(1, r // 18),
                )
            for index in (-1, 0, 1):
                leaf = [
                    (x, y - round(r * 0.78)),
                    (x + round(r * (index * 0.48 - 0.18)), y - round(r * 1.25)),
                    (x + round(r * (index * 0.48 + 0.12)), y - round(r * 0.8)),
                ]
                pygame.draw.polygon(surface, LEAF, leaf)
        elif fruit_id in {"melon", "watermelon"}:
            stripe = (82, 145, 78) if fruit_id == "watermelon" else _shade(color, 0.78)
            for offset in (-0.66, -0.34, 0, 0.34, 0.66):
                half_height = round(r * (0.9 - abs(offset) * 0.23))
                rect = (
                    x + round(r * offset) - max(2, r // 12),
                    y - half_height,
                    max(4, r // 6),
                    half_height * 2,
                )
                pygame.draw.ellipse(surface, stripe, rect)

    @staticmethod
    def _draw_face(pygame: Any, surface: Surface, center: tuple[int, int], radius: int) -> None:
        x, y = center
        eye_y = y - round(radius * 0.08)
        eye_spacing = round(radius * 0.3)
        eye_radius = max(2, round(radius * 0.18))
        pupil_radius = max(1, round(eye_radius * 0.48))
        for eye_x in (x - eye_spacing, x + eye_spacing):
            pygame.draw.circle(surface, OUTLINE, (eye_x, eye_y), eye_radius + max(1, radius // 30))
            pygame.draw.circle(surface, CREAM, (eye_x, eye_y), eye_radius)
            pygame.draw.circle(surface, OUTLINE, (eye_x + pupil_radius // 3, eye_y), pupil_radius)
            pygame.draw.circle(
                surface,
                (255, 255, 255),
                (eye_x, eye_y - pupil_radius // 3),
                max(1, pupil_radius // 3),
            )
        mouth_rect = (
            x - round(radius * 0.22),
            y + round(radius * 0.02),
            round(radius * 0.44),
            round(radius * 0.34),
        )
        pygame.draw.arc(surface, OUTLINE, mouth_rect, 0.15, pi - 0.15, max(1, radius // 16))


__all__ = ["ProceduralArt"]
