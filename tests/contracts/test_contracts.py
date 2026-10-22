from __future__ import annotations

import subprocess
import sys
from dataclasses import FrozenInstanceError

import pytest

from suika_elika.contracts import (
    UNKNOWN_PLAYER_ID,
    AudioPort,
    ControllerProfileData,
    DomainEvent,
    EventType,
    FruitDefinition,
    FruitSnapshot,
    GameResultData,
    InputAction,
    InputEdge,
    InputEdgeQueue,
    InputFrame,
    PlayerData,
    Pose,
    RecordCheckpointData,
    RecordData,
    RoundState,
    SessionSnapshot,
    SettingsData,
    StatisticsData,
    Vector2,
    normalize_player_name,
)


def sample_fruit() -> FruitDefinition:
    return FruitDefinition(
        fruit_id="cherry",
        level=1,
        radius=14.0,
        mass=1.0,
        points_on_spawn=0,
        visual_key="fruit.cherry",
    )


def test_public_models_are_immutable_and_snapshots_are_copied_values() -> None:
    pose = Pose(Vector2(10.0, 20.0))
    fruit = FruitSnapshot("fruit-1", "cherry", pose, pose, False, 0.0)
    snapshot = SessionSnapshot(
        score=0,
        high_score=0,
        current_fruit=sample_fruit(),
        next_fruit=None,
        fruits=(fruit,),
        launcher_x=640.0,
        drop_ready=True,
        danger_progress=0.0,
        round_state=RoundState.READY,
    )

    assert snapshot.fruits[0].current_pose.position == Vector2(10.0, 20.0)
    with pytest.raises(FrozenInstanceError):
        fruit.entity_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.score = 10  # type: ignore[misc]
    with pytest.raises(TypeError, match="immutable tuple"):
        SessionSnapshot(0, 0, None, None, [], 0.0, True, 0.0, RoundState.READY)  # type: ignore[arg-type]


def test_contract_imports_do_not_import_or_initialize_engine_libraries() -> None:
    script = """
import sys
import suika_elika.contracts
from suika_elika.contracts import events, input, models, ports

assert not any(name == "pygame" or name.startswith("pygame.") for name in sys.modules)
assert not any(name == "pymunk" or name.startswith("pymunk.") for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_input_edges_are_consumed_once_and_invalid_commands_do_not_remain_queued() -> None:
    queue = InputEdgeQueue()
    drop = InputEdge(sequence=1, action=InputAction.DROP)
    pause = InputEdge(sequence=2, action=InputAction.PAUSE)
    queue.enqueue_frame(InputFrame(move_x=0.5, fine_adjust=True, edges=(drop, pause)))

    first_eligible_step = queue.consume_for_step()
    assert first_eligible_step == (drop, pause)
    # A consumer may reject these edges because the launcher is blocked. They
    # have still been drained and cannot trigger on a later physics substep.
    assert queue.consume_for_step() == ()


def test_input_frame_carries_vertical_navigation_and_directional_actions() -> None:
    navigation = InputEdge(1, InputAction.NAV_UP)
    frame = InputFrame(move_y=-0.6, edges=(navigation,))

    assert frame.move_y == -0.6
    assert frame.edges == (navigation,)


def test_input_contract_rejects_non_normalized_motion_and_duplicate_edges() -> None:
    with pytest.raises(ValueError, match="normalized"):
        InputFrame(move_x=1.1)
    with pytest.raises(ValueError, match="move_y"):
        InputFrame(move_y=-1.1)
    edge = InputEdge(sequence=3, action=InputAction.CONFIRM)
    with pytest.raises(ValueError, match="unique"):
        InputFrame(edges=(edge, edge))


def test_edge_queue_requires_monotonic_sequences_but_keeps_sequence_after_clear() -> None:
    queue = InputEdgeQueue()
    queue.enqueue(InputEdge(4, InputAction.DROP))
    queue.clear()
    with pytest.raises(ValueError, match="increase monotonically"):
        queue.enqueue(InputEdge(4, InputAction.DROP))
    queue.enqueue(InputEdge(5, InputAction.DROP))


def test_domain_event_payload_cannot_retain_mutable_engine_or_callback_objects() -> None:
    with pytest.raises(TypeError, match="immutable primitives"):
        DomainEvent(EventType.FRUIT_MERGED, 10, payload=(("arbiter", object()),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        DomainEvent(EventType.DANGER_CHANGED, 10, payload=(("seconds", float("nan")),))
    event = DomainEvent(
        EventType.FRUIT_MERGED,
        10,
        entity_ids=("a", "b"),
        position=Vector2(2.0, 3.0),
        payload=(("fruit_id", "apple"), ("score", 1)),
    )
    assert event.entity_ids == ("a", "b")


def test_audio_protocol_accepts_a_silent_structural_adapter() -> None:
    class SilentAudio:
        def consume(self, events: tuple[DomainEvent, ...]) -> None:
            del events

        def set_gains(self, *, master: float, effects: float, music: float) -> None:
            del master, effects, music

        def pause(self) -> None:
            pass

        def resume(self) -> None:
            pass

        def close(self) -> None:
            pass

    audio: AudioPort = SilentAudio()
    assert isinstance(audio, SilentAudio)


def test_settings_data_validates_persisted_gain_range() -> None:
    assert SettingsData().master_gain == 0.8
    with pytest.raises(ValueError, match="between 0 and 1"):
        SettingsData(master_gain=1.1)
    with pytest.raises(ValueError, match="safe area"):
        SettingsData(safe_area_fraction=0.3)
    with pytest.raises(ValueError, match="safe area"):
        SettingsData(safe_area_fraction=True)  # type: ignore[arg-type]
    assert SettingsData(fruit_hitbox_scales=(("apple", 1.25),)).fruit_hitbox_scales == (
        ("apple", 1.25),
    )
    with pytest.raises(ValueError, match="hitbox scales"):
        SettingsData(fruit_hitbox_scales=(("apple", 1.6),))
    with pytest.raises(ValueError, match="hitbox scales"):
        SettingsData(fruit_hitbox_scales=(("apple", 1.0), ("apple", 1.1)))
    assert SettingsData(fullscreen=False, safe_area_fraction=0.1).safe_area_fraction == 0.1


def test_record_data_keeps_mode_and_duration_and_validates_both() -> None:
    record = RecordData("classic-v1", 10, 4, 1, mode="classic", duration_seconds=42.5)
    assert (record.mode, record.duration_seconds) == ("classic", 42.5)
    with pytest.raises(ValueError, match="duration"):
        RecordData("classic-v1", 10, 4, 1, duration_seconds=float("nan"))


def test_profile_and_statistics_contracts_validate_stable_data() -> None:
    profile = ControllerProfileData(
        profile_id="pad",
        name="Gamepad",
        backend="controller",
        bindings=(("drop", "south"),),
        platform="linux",
        guid="guid-1",
        axes=(("move_x", 0),),
        inverted_axes=("move_x",),
        deadzone=0.2,
        sensitivity=1.3,
    )
    assert profile.axes == (("move_x", 0),)
    assert StatisticsData(sessions_played=2).sessions_played == 2
    with pytest.raises(ValueError, match="deadzone"):
        ControllerProfileData("pad", "Gamepad", "controller", (), deadzone=1.0)
    with pytest.raises(ValueError, match="deadzone"):
        ControllerProfileData("pad", "Gamepad", "controller", (), deadzone=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative integers"):
        StatisticsData(merges=-1)


def test_player_name_normalization_and_reserved_unknown() -> None:
    assert normalize_player_name("  Jose\u0301   Silva ") == "José Silva"
    assert len(normalize_player_name("a" * 20)) == 20
    for name in ("", "a" * 21, " desconhecido "):
        with pytest.raises(ValueError):
            normalize_player_name(name)
    assert PlayerData("player-1", "Ana").name == "Ana"
    assert UNKNOWN_PLAYER_ID == "unknown"


def test_result_and_checkpoint_contracts_and_horizontal_input() -> None:
    result = GameResultData("result-1", UNKNOWN_PLAYER_ID, "classic", "v1", "none", 2000, 210.0)
    checkpoint = RecordCheckpointData(
        "result-1", UNKNOWN_PLAYER_ID, "classic", "v1", "none", 2000, 80.0
    )
    assert result.result_id == checkpoint.result_id
    assert InputAction.NAV_LEFT.value == "nav_left"
    assert InputAction.NAV_RIGHT.value == "nav_right"


@pytest.mark.parametrize("score", (-1, True))
def test_result_rejects_invalid_score(score: int) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        GameResultData("result-1", UNKNOWN_PLAYER_ID, "classic", "v1", "none", score, 10.0)


@pytest.mark.parametrize("duration", (-1.0, float("inf"), float("nan")))
def test_result_rejects_invalid_duration(duration: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        GameResultData("result-1", UNKNOWN_PLAYER_ID, "classic", "v1", "none", 1, duration)


def test_player_data_requires_a_normalized_non_reserved_identity() -> None:
    with pytest.raises(ValueError, match="already be normalized"):
        PlayerData("player-1", " Ana ")
    with pytest.raises(ValueError, match="not reserved"):
        PlayerData(UNKNOWN_PLAYER_ID, "Ana")
