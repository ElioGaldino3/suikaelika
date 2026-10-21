"""Immediate taps and 180 BPM holds over real Pymunk worlds and scene queues."""

from collections import defaultdict
from types import SimpleNamespace

import pytest

from suika_elika.app import _KeyboardAdapter
from suika_elika.contracts import EventType, InputAction, InputEdge, InputFrame
from suika_elika.game.battle import BattleSession
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.scenes.battle import BattleScene
from suika_elika.scenes.play import PlayScene


def press(sequence=0, *, held=True):
    return InputFrame(drop_held=held, edges=(InputEdge(sequence, InputAction.DROP),))


@pytest.mark.parametrize("seed", [0, 2, 31])
@pytest.mark.parametrize("fps", [30, 60, 120])
def test_hold_launches_on_333ms_beats_with_real_physics_independent_of_render_fps(seed, fps):
    session = GameSession(PhysicsWorld(), seed=seed)
    scene = PlayScene(session)
    scene.enter()
    ticks = []
    tick = 0
    for render_frame in range(fps):
        scene.handle_actions(press() if render_frame == 0 else InputFrame(drop_held=True))
        for _ in range(120 // fps):
            events = scene.simulation_step()
            ticks.extend(tick for event in events if event.event_type is EventType.FRUIT_DROPPED)
            tick += 1
    assert ticks == [0, 40, 80]
    assert session.drop_count == 3


def test_taps_are_immediate_even_within_150ms_in_real_world():
    session = GameSession(PhysicsWorld())
    session._launcher.set_launcher_x(100)
    session.step(press(0, held=False))
    session._launcher.set_launcher_x(300)
    events = session.step(press(1, held=False))
    assert session.drop_count == 2
    assert any(e.event_type is EventType.FRUIT_DROPPED for e in events)
    for _ in range(120):
        session.step()
    assert session.drop_count == 2


def test_release_and_pause_disarm_hold_until_a_fresh_press():
    session = GameSession(PhysicsWorld())
    session.step(press())
    for _ in range(39):
        session.step(InputFrame(drop_held=True))
    session.pause()
    for _ in range(120):
        session.step(InputFrame(drop_held=True))
    session.resume()
    for _ in range(120):
        session.step(InputFrame(drop_held=True))
    assert session.drop_count == 1
    session.step(press(1))
    assert session.drop_count == 2
    session.step(InputFrame())
    for _ in range(120):
        session.step(InputFrame(drop_held=True))
    assert session.drop_count == 2


def test_menu_confirmation_hold_does_not_arm_a_new_round():
    scene = PlayScene(GameSession(PhysicsWorld()))
    scene.enter()
    scene.handle_actions(InputFrame(drop_held=True))
    for _ in range(180):
        scene.simulation_step()
    assert scene.session.drop_count == 0


def test_blocked_repeat_is_skipped_without_backlog_or_burst(monkeypatch):
    world = PhysicsWorld()
    blocked = True
    monkeypatch.setattr(world, "overlaps", lambda *_: ("pile",) if blocked else ())
    session = GameSession(world)
    session.step(press())
    for _ in range(40):
        session.step(InputFrame(drop_held=True))
    assert session.drop_count == 0
    blocked = False
    for _ in range(39):
        session.step(InputFrame(drop_held=True))
    assert session.drop_count == 0
    session.step(InputFrame(drop_held=True))
    assert session.drop_count == 1  # tick 80, rather than a burst when the mouth clears


def test_battle_holds_and_releases_are_independent_for_both_players():
    battle = BattleSession()
    scene = BattleScene(battle)
    scene.enter()
    for tick in range(120):
        scene.handle_players(
            (
                press() if tick == 0 else InputFrame(drop_held=True),
                press() if tick == 0 else InputFrame(drop_held=tick < 36),
            )
        )
        scene.simulation_step()
    assert [player.drop_count for player in battle.players] == [3, 1]


def test_keyboard_reports_hold_separately_and_ignores_operating_system_repeat():
    pressed = defaultdict(bool)
    pygame = SimpleNamespace(
        KEYDOWN=1,
        K_SPACE=32,
        K_RETURN=13,
        K_ESCAPE=27,
        K_p=112,
        K_LEFT=276,
        K_RIGHT=275,
        K_UP=273,
        K_DOWN=274,
        K_LSHIFT=304,
        key=SimpleNamespace(get_pressed=lambda: pressed),
    )
    adapter = _KeyboardAdapter(pygame)
    pressed[pygame.K_SPACE] = True
    adapter.process_events((SimpleNamespace(type=1, key=32, repeat=False),))
    first = adapter.poll()
    assert first.drop_held and first.action_edges == (InputAction.DROP,)
    adapter.process_events((SimpleNamespace(type=1, key=32, repeat=True),))
    held = adapter.poll()
    assert held.drop_held and held.action_edges == ()
    adapter.clear()
    assert adapter.poll().action_edges == ()
    pressed[pygame.K_SPACE] = False
    assert not adapter.poll().drop_held
