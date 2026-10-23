"""Load the supplied game art, with a procedural fallback for source-only runs."""

from __future__ import annotations

from importlib import import_module
from math import hypot
from pathlib import Path
from typing import Any

from suika_elika.game.catalog import FruitCatalog
from suika_elika.rendering.procedural import ProceduralArt

Surface = Any
ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"


def cover_surface(pygame: Any, source: Surface, size: tuple[int, int]) -> Surface:
    """Scale an image to cover a target while preserving its aspect ratio."""
    width, height = source.get_size()
    target_width, target_height = size
    scale = max(target_width / width, target_height / height)
    scaled_size = (round(width * scale), round(height * scale))
    scaled = pygame.transform.smoothscale(source, scaled_size)
    left = (scaled_size[0] - target_width) // 2
    top = (scaled_size[1] - target_height) // 2
    return scaled.subsurface((left, top, target_width, target_height)).copy()


class GameArt:
    """Serve cached imported fruit sprites and backgrounds when packaged."""

    def __init__(self, asset_root: Path = ASSET_ROOT) -> None:
        self._pygame = import_module("pygame")
        self._asset_root = asset_root
        self._fallback = ProceduralArt()
        self._fruit_cache: dict[tuple[str, float], Surface] = {}
        self._background_cache: dict[tuple[str, tuple[int, int]], Surface] = {}

    def fruit_surfaces(self, catalog: FruitCatalog) -> dict[str, Surface]:
        """Build catalog sprites at their intended visual envelope once."""
        result: dict[str, Surface] = {}
        sprite_dir = self._asset_root / "sprites"
        for entry in catalog.entries:
            path = sprite_dir / f"{entry.fruit_id}.png"
            if not path.is_file():
                result[entry.fruit_id] = self._fallback.fruit_surface(entry)
                continue
            radius = max(12, round(entry.definition.radius))
            margin = max(7, round(radius * 0.28))
            side = (radius + margin) * 2
            collision_radius = float(entry.definition.radius)
            key = (entry.fruit_id, round(collision_radius, 4))
            surface = self._fruit_cache.get(key)
            if surface is None:
                source = self._pygame.image.load(path)
                width, height = source.get_size()
                silhouette = self._pygame.mask.from_surface(source, 32)
                center_x = width / 2
                center_y = height / 2
                outline_points = (
                    point
                    for component in silhouette.connected_components()
                    for point in component.outline()
                )
                silhouette_radius = max(
                    (
                        hypot(x + 0.5 - center_x, y + 0.5 - center_y)
                        for x, y in outline_points
                    ),
                    default=0.0,
                )
                if silhouette_radius <= 0:
                    result[entry.fruit_id] = self._fallback.fruit_surface(entry)
                    continue
                scale = collision_radius / silhouette_radius
                # Even dimensions keep the source center on the integer center
                # of the destination, avoiding a half-pixel collision offset.
                size = (
                    max(2, 2 * round(width * scale / 2)),
                    max(2, 2 * round(height * scale / 2)),
                )
                fitted = self._pygame.transform.smoothscale(source, size)
                surface = self._pygame.Surface(
                    (side, side), self._pygame.SRCALPHA, 32
                )
                surface.blit(fitted, fitted.get_rect(center=(side // 2, side // 2)))
                self._fruit_cache[key] = surface
            result[entry.fruit_id] = surface
        return result

    def background_surface(
        self, size: tuple[int, int] = (1280, 720), *, menu: bool = False,
        battle: bool = False,
    ) -> Surface:
        """Return a cached imported background or the procedural fallback."""
        name = "battle.png" if battle else "menu.png" if menu else "gameplay.png"
        path = self._asset_root / "backgrounds" / name
        if not path.is_file():
            return self._fallback.background_surface(size)
        key = (name, size)
        surface = self._background_cache.get(key)
        if surface is None:
            source = self._pygame.image.load(path)
            surface = cover_surface(self._pygame, source, size)
            self._background_cache[key] = surface
        return surface

    def container_surface(self, size: tuple[int, int] = (800, 460)) -> Surface:
        return self._fallback.container_surface(size)


__all__ = ["ASSET_ROOT", "GameArt", "cover_surface"]
