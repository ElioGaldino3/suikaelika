"""Crop the supplied fruit sheet and prepare 16:9 game backgrounds.

Run from the repository root with the game's Pygame installed:
    python tools/process_art_assets.py
The user-provided files in raw_assets/ are read-only inputs.
"""

from __future__ import annotations

from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "raw_assets"
OUTPUT = ROOT / "assets"
LOGICAL_SIZE = (1280, 720)

# Cells follow classic-v1.json: six upper-row fruits, then five lower-row fruits.
# Boundaries sit in the clear gaps between drawings, including their shadows.
FRUIT_CELLS = {
    "cherry": (18, 210, 166, 461),
    "strawberry": (162, 202, 327, 465),
    "grape": (330, 176, 550, 457),
    "lemon": (556, 154, 790, 480),
    "apple": (795, 141, 1088, 480),
    "orange": (1090, 127, 1445, 478),
    "pear": (0, 485, 220, 984),
    "peach": (228, 493, 475, 987),
    "pineapple": (479, 475, 730, 1000),
    "melon": (735, 489, 1018, 996),
    "watermelon": (1028, 480, 1448, 1016),
}


def remove_edge_background(image: pygame.Surface) -> pygame.Surface:
    """Make near-white pixels connected to the crop edge transparent."""
    rgba = pygame.Surface(image.get_size(), pygame.SRCALPHA, 32)
    rgba.blit(image, (0, 0))
    white = pygame.mask.from_threshold(
        rgba,
        (253, 253, 253, 255),
        (12, 12, 12, 255),
    )
    width, height = rgba.get_size()
    edge = pygame.mask.Mask((width, height))
    edge.draw(pygame.mask.Mask((width, 1), fill=True), (0, 0))
    edge.draw(pygame.mask.Mask((width, 1), fill=True), (0, height - 1))
    edge.draw(pygame.mask.Mask((1, height), fill=True), (0, 0))
    edge.draw(pygame.mask.Mask((1, height), fill=True), (width - 1, 0))

    background = pygame.mask.Mask((width, height))
    for component in white.connected_components():
        if component.overlap_area(edge, (0, 0)):
            background.draw(component, (0, 0))

    alpha = background.to_surface(
        setcolor=(255, 255, 255, 0), unsetcolor=(255, 255, 255, 255)
    )
    rgba.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return rgba


def trim_transparent(image: pygame.Surface, padding: int = 8) -> pygame.Surface:
    bounds = image.get_bounding_rect(min_alpha=1)
    if bounds.width <= 0 or bounds.height <= 0:
        raise ValueError("fruit crop contains no opaque pixels")
    left = max(0, bounds.left - padding)
    top = max(0, bounds.top - padding)
    right = min(image.get_width(), bounds.right + padding)
    bottom = min(image.get_height(), bounds.bottom + padding)
    bounds = pygame.Rect(left, top, right - left, bottom - top)
    return image.subsurface(bounds).copy()


def fit_cover(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Scale and center-crop a source image to the logical 16:9 canvas."""
    width, height = image.get_size()
    target_width, target_height = size
    scale = max(target_width / width, target_height / height)
    scaled_size = (round(width * scale), round(height * scale))
    scaled = pygame.transform.smoothscale(image, scaled_size)
    left = (scaled_size[0] - target_width) // 2
    top = (scaled_size[1] - target_height) // 2
    output = pygame.Surface(size)
    output.blit(scaled, (-left, -top))
    return output


def main() -> None:
    pygame.init()
    try:
        sheet = pygame.image.load(SOURCE / "frutinhas.png")
        sprite_dir = OUTPUT / "sprites"
        sprite_dir.mkdir(parents=True, exist_ok=True)
        for fruit_id, cell in FRUIT_CELLS.items():
            x1, y1, x2, y2 = cell
            cropped = sheet.subsurface((x1, y1, x2 - x1, y2 - y1)).copy()
            sprite = trim_transparent(remove_edge_background(cropped))
            pygame.image.save(sprite, sprite_dir / f"{fruit_id}.png")

        background_dir = OUTPUT / "backgrounds"
        background_dir.mkdir(parents=True, exist_ok=True)
        for source_name, output_name in (
            ("background_menu.png", "menu.png"),
            ("background_jogo.png", "gameplay.png"),
        ):
            background = pygame.image.load(SOURCE / source_name)
            pygame.image.save(
                fit_cover(background, LOGICAL_SIZE), background_dir / output_name
            )
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
