"""Real surface composition and packaged battle background checks."""

from dataclasses import replace

import pytest

pygame = pytest.importorskip("pygame")

from suika_elika.app import _MenuCanvas  # noqa: E402
from suika_elika.contracts import FruitSnapshot, Pose, Vector2  # noqa: E402
from suika_elika.game.battle import BattleSession  # noqa: E402
from suika_elika.rendering.assets import ASSET_ROOT, GameArt  # noqa: E402
from suika_elika.rendering.battle import BattleRenderer  # noqa: E402
from suika_elika.rendering.renderer import DEBUG_COLLIDER_COLOR  # noqa: E402
from suika_elika.scenes.title import TitleScene  # noqa: E402


@pytest.fixture(autouse=True)
def fonts():
    pygame.font.init()


def demo_snapshot():
    battle = BattleSession(seed=31)
    snapshot = battle.snapshot
    players = []
    for index, player in enumerate(snapshot.players):
        fruits = []
        for number, fruit_id in enumerate(("watermelon", "pineapple", "orange", "apple")):
            pose = Pose(Vector2(110 + number * 90, 350 - number * 30), 0)
            fruits.append(FruitSnapshot(f"demo-{number}", fruit_id, pose, pose, False, 0))
        players.append(replace(player, score=275 + index * 65, fruits=tuple(fruits)))
    return replace(snapshot, players=(players[0], players[1]))


def test_battle_background_uses_the_packaged_art() -> None:
    packaged = pygame.image.load(ASSET_ROOT / "backgrounds" / "battle.png")
    actual = GameArt().background_surface(battle=True)
    for point in ((50, 50), (640, 360), (1200, 650)):
        assert actual.get_at(point) == packaged.get_at(point)


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (800, 600)])
def test_battle_has_two_baskets_and_uses_safe_viewport(size) -> None:
    target = pygame.Surface(size)
    renderer = BattleRenderer(target)
    renderer.draw_battle(demo_snapshot())
    canvas = renderer._logical
    assert canvas.get_at((80, 300))[:3] == (126, 219, 255)
    assert canvas.get_at((720, 300))[:3] == (255, 185, 119)
    assert canvas.get_at((640, 300))[:3] == (255, 230, 172)
    x, y, width, height = renderer.presentation_rect
    assert 0 <= x < size[0] and 0 <= y < size[1]
    assert x + width <= size[0] and y + height <= size[1]


def test_battle_debug_flag_draws_active_fruit_colliders() -> None:
    renderer = BattleRenderer(pygame.Surface((1280, 720)), debug_colliders=True)
    snapshot = demo_snapshot()
    fruit = snapshot.players[0].fruits[-1]
    definition = renderer.catalog.get(fruit.fruit_id).definition
    center = (
        80 + round(fruit.current_pose.position.x),
        180 + round(fruit.current_pose.position.y),
    )

    renderer.draw_battle(snapshot)

    assert (
        renderer._logical.get_at((center[0] + round(definition.radius) - 1, center[1]))[:3]
        == DEBUG_COLLIDER_COLOR
    )


def test_title_renders_disabled_battle_without_hiding_it() -> None:
    target = pygame.Surface((1280, 720))
    canvas = _MenuCanvas(pygame, target)
    scene = TitleScene()
    assert scene.snapshot.disabled_indices == (1,)
    canvas.draw_menu(scene.snapshot)
