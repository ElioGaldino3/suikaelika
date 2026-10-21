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
FRUIT_SHEET = SOURCE / "frutinhas_v2.png"
FRUIT_SHEET_SIZE = (1536, 1024)
LOGICAL_SIZE = (1280, 720)

# Alpha-aware cells follow the classic catalog: six upper-row fruits, then five
# lower-row fruits. The bounds fit between the visible, non-transparent drawings.
FRUIT_CELLS = {
    "cherry": (0, 0, 187, 480),
    "strawberry": (187, 0, 411, 480),
    "grape": (411, 0, 670, 480),
    "lemon": (670, 0, 924, 480),
    "apple": (924, 0, 1217, 480),
    "orange": (1217, 0, 1536, 480),
    "pear": (0, 480, 270, 1024),
    "peach": (270, 480, 557, 1024),
    "pineapple": (557, 480, 833, 1024),
    "melon": (833, 480, 1129, 1024),
    "watermelon": (1129, 480, 1536, 1024),
}


def trim_transparent(
    image: pygame.Surface, padding: int = 8, min_alpha: int = 32
) -> pygame.Surface:
    """Trim only the nearly invisible outer glow, keeping source pixels intact."""
    if type(padding) is not int or padding < 0:
        raise ValueError("padding must be a non-negative integer")
    if type(min_alpha) is not int or not 1 <= min_alpha <= 255:
        raise ValueError("min_alpha must be an integer in [1, 255]")
    bounds = image.get_bounding_rect(min_alpha=min_alpha)
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
        sheet = pygame.image.load(FRUIT_SHEET)
        if sheet.get_size() != FRUIT_SHEET_SIZE:
            raise ValueError(
                f"expected {FRUIT_SHEET_SIZE} fruit sheet, got {sheet.get_size()}"
            )
        sprite_dir = OUTPUT / "sprites"
        sprite_dir.mkdir(parents=True, exist_ok=True)
        for fruit_id, cell in FRUIT_CELLS.items():
            x1, y1, x2, y2 = cell
            cropped = sheet.subsurface((x1, y1, x2 - x1, y2 - y1)).copy()
            sprite = trim_transparent(cropped)
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
