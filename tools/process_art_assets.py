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
FRUIT_SHEET = SOURCE / "frutinhas_v3.png"
FRUIT_SHEET_SIZE = (1448, 1086)
LOGICAL_SIZE = (1280, 720)

# Cells follow the classic catalog: six upper-row fruits, then five lower-row
# fruits. Empty separator gaps are left out where neighboring glow pixels touch.
FRUIT_CELLS = {
    "cherry": (0, 0, 210, 600),
    "strawberry": (213, 0, 436, 600),
    "grape": (439, 0, 674, 600),
    "lemon": (674, 0, 907, 600),
    "apple": (909, 0, 1182, 600),
    "orange": (1182, 0, 1448, 600),
    "pear": (0, 600, 266, 1086),
    "peach": (268, 600, 541, 1086),
    "pineapple": (545, 600, 812, 1086),
    "melon": (812, 600, 1097, 1086),
    "watermelon": (1098, 600, 1448, 1086),
}


def trim_transparent(
    image: pygame.Surface, padding: int = 8, min_alpha: int = 32
) -> pygame.Surface:
    """Trim only the nearly invisible outer glow, keeping source pixels intact."""
    if type(padding) is not int or padding < 0:
        raise ValueError("padding must be a non-negative integer")
    if type(min_alpha) is not int or not 1 <= min_alpha <= 255:
        raise ValueError("min_alpha must be an integer in [1, 255]")
    content_bounds = image.get_bounding_rect(min_alpha=min_alpha)
    if content_bounds.width <= 0 or content_bounds.height <= 0:
        raise ValueError("fruit crop contains no opaque pixels")
    left = max(0, content_bounds.left - padding)
    top = max(0, content_bounds.top - padding)
    right = min(image.get_width(), content_bounds.right + padding)
    bottom = min(image.get_height(), content_bounds.bottom + padding)
    bounds = pygame.Rect(left, top, right - left, bottom - top)
    cropped = image.subsurface(bounds).copy()
    missing_padding = (
        max(0, padding - content_bounds.left),
        max(0, padding - content_bounds.top),
        max(0, padding - (image.get_width() - content_bounds.right)),
        max(0, padding - (image.get_height() - content_bounds.bottom)),
    )
    if not any(missing_padding):
        return cropped
    left_pad, top_pad, right_pad, bottom_pad = missing_padding
    padded = pygame.Surface(
        (
            cropped.get_width() + left_pad + right_pad,
            cropped.get_height() + top_pad + bottom_pad,
        ),
        pygame.SRCALPHA,
        32,
    )
    padded.blit(cropped, (left_pad, top_pad))
    return padded


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


def process_fruit_sprites(sheet: pygame.Surface, sprite_dir: Path) -> None:
    """Crop the v3 fruit sheet into native-resolution transparent PNGs."""
    if sheet.get_size() != FRUIT_SHEET_SIZE:
        raise ValueError(
            f"expected {FRUIT_SHEET_SIZE} fruit sheet, got {sheet.get_size()}"
        )
    sprite_dir.mkdir(parents=True, exist_ok=True)
    for fruit_id, cell in FRUIT_CELLS.items():
        x1, y1, x2, y2 = cell
        cropped = sheet.subsurface((x1, y1, x2 - x1, y2 - y1)).copy()
        sprite = trim_transparent(cropped)
        pygame.image.save(sprite, sprite_dir / f"{fruit_id}.png")


def main() -> None:
    pygame.init()
    try:
        sheet = pygame.image.load(FRUIT_SHEET)
        sprite_dir = OUTPUT / "sprites"
        process_fruit_sprites(sheet, sprite_dir)

        background_dir = OUTPUT / "backgrounds"
        background_dir.mkdir(parents=True, exist_ok=True)
        for source_name, output_name in (
            ("background_menu.png", "menu.png"),
            ("background_jogo.png", "gameplay.png"),
            ("battle_background.png", "battle.png"),
        ):
            background = pygame.image.load(SOURCE / source_name)
            pygame.image.save(
                fit_cover(background, LOGICAL_SIZE), background_dir / output_name
            )
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
