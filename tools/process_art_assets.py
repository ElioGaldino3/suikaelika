"""Pack individually generated round fruits and prepare 16:9 backgrounds.

Run from the repository root with the game's Pygame installed:
    python tools/process_art_assets.py
The user-provided files in raw_assets/ are read-only inputs.
Pass --fruit-source DIR to replace sprites; the default only rebuilds backgrounds.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "raw_assets"
OUTPUT = ROOT / "assets"
FRUIT_SHEET = SOURCE / "frutinhas_v3.png"
FRUIT_SHEET_SIZE = (1448, 1086)
LOGICAL_SIZE = (1280, 720)
SPRITE_SIZE = 512
SPRITE_RADIUS = 248

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
    """Extract historical sheet crops, independently of the current round assets."""
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


def pack_round_sprite(source: pygame.Surface) -> pygame.Surface:
    """Resize generated art and enforce the shared circular alpha envelope.

    The source must already depict a round fruit. A small overscan hides minor
    generated contour irregularities; reject art requiring more than 10% crop.
    This prepares pixels only, without changing the gameplay collision radius.
    """
    bounds = source.get_bounding_rect(min_alpha=32)
    if not bounds.width or not bounds.height:
        raise ValueError("fruit source contains no opaque pixels")
    if not 0.9 <= bounds.width / bounds.height <= 1.1:
        raise ValueError("fruit source must already have a round silhouette")
    cropped = source.subsurface(bounds)
    side = SPRITE_SIZE
    # Supersample only the geometric mask, retaining the generated artwork.
    mask = pygame.Surface((side * 4, side * 4), pygame.SRCALPHA, 32)
    pygame.draw.circle(mask, (255, 255, 255, 255), (side * 2, side * 2), SPRITE_RADIUS * 4)
    mask = pygame.transform.smoothscale(mask, (side, side))
    required = pygame.mask.from_surface(mask, 0)
    for diameter in range(SPRITE_RADIUS * 2, round(SPRITE_RADIUS * 2 * 1.1) + 1, 2):
        fitted = pygame.transform.smoothscale(cropped, (diameter, diameter))
        sprite = pygame.Surface((side, side), pygame.SRCALPHA, 32)
        sprite.blit(fitted, fitted.get_rect(center=(side // 2, side // 2)))
        visible = pygame.mask.from_surface(sprite, 240)
        if visible.overlap_area(required, (0, 0)) == required.count():
            # Resampling may lower even interior alpha slightly. Coverage is
            # verified above, so make the body opaque before applying its edge.
            sprite.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MAX)
            sprite.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return sprite
    raise ValueError("fruit source does not fill the circular envelope; regenerate it")


def process_round_fruits(source_dir: Path, sprite_dir: Path) -> None:
    """Validate the entire set before replacing any of the packaged sprites."""
    sprites = {
        fruit_id: pack_round_sprite(pygame.image.load(source_dir / f"{fruit_id}.png"))
        for fruit_id in FRUIT_CELLS
    }
    sprite_dir.mkdir(parents=True, exist_ok=True)
    for fruit_id, sprite in sprites.items():
        pygame.image.save(sprite, sprite_dir / f"{fruit_id}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fruit-source", type=Path, help="directory of 11 generated round PNGs")
    args = parser.parse_args()
    pygame.init()
    try:
        if args.fruit_source is not None:
            process_round_fruits(args.fruit_source, OUTPUT / "sprites")
            return

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
