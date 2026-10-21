from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from wave import open as open_wave

import pytest

from suika_elika.audio import (
    NullAudioManager,
    PygameAudioManager,
    create_audio_manager,
)
from suika_elika.contracts.events import DomainEvent, EventType, EventValue


def _event(event_type: EventType, **payload_values: EventValue) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        step_index=1,
        payload=tuple((key, value) for key, value in payload_values.items()),
    )


@dataclass
class FakeSound:
    name: str


class FakeChannel:
    def __init__(self, channel_id: int, mixer: FakeMixer) -> None:
        self.channel_id = channel_id
        self.mixer = mixer
        self.busy = False
        self.volume = 1.0
        self.paused = False
        self.stop_count = 0

    def get_busy(self) -> bool:
        return self.busy

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def play(self, sound: FakeSound) -> None:
        self.busy = True
        self.mixer.played.append((self.channel_id, sound.name))

    def stop(self) -> None:
        self.stop_count += 1
        self.busy = False

    def pause(self) -> None:
        self.paused = True

    def unpause(self) -> None:
        self.paused = False


class FakeMixer:
    def __init__(self, *, initialized: bool = False, fail_init: bool = False) -> None:
        self.initialized = initialized
        self.fail_init = fail_init
        self.init_args: dict[str, int] | None = None
        self.quit_count = 0
        self.channels: list[FakeChannel] = []
        self.played: list[tuple[int, str]] = []
        self._sound_count = 0

    def get_init(self) -> tuple[int, int, int] | None:
        return (44_100, -16, 2) if self.initialized else None

    def init(self, **kwargs: int) -> None:
        self.init_args = kwargs
        if self.fail_init:
            raise RuntimeError("audio device unavailable")
        self.initialized = True

    def set_num_channels(self, count: int) -> None:
        self.channels = [FakeChannel(index, self) for index in range(count)]

    def Channel(self, index: int) -> FakeChannel:
        return self.channels[index]

    def Sound(self, *, file: BytesIO) -> FakeSound:
        with open_wave(file, "rb") as wav:
            assert wav.getnchannels() == 2
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 44_100
            assert wav.getnframes() > 0
        names = ("drop", "merge", "watermelon", "warning", "result")
        sound = FakeSound(names[self._sound_count])
        self._sound_count += 1
        return sound

    def quit(self) -> None:
        self.quit_count += 1
        self.initialized = False


class FakePygame:
    def __init__(self, mixer: FakeMixer) -> None:
        self.mixer = mixer


def test_manager_builds_original_pcm_effects_and_sets_mixer_before_channels() -> None:
    mixer = FakeMixer()
    manager = PygameAudioManager(FakePygame(mixer))

    assert manager.available
    assert mixer.init_args == {
        "frequency": 44_100,
        "size": -16,
        "channels": 2,
        "buffer": 512,
    }
    assert len(mixer.channels) == 16
    manager.set_gains(master=0.5, effects=0.4, music=0.2)
    assert manager.gains == (0.5, 0.4, 0.2)
    assert all(channel.volume == pytest.approx(0.2) for channel in mixer.channels)


def test_event_priority_routes_effects_and_result_suppresses_lower_priority_events() -> None:
    mixer = FakeMixer(initialized=True)
    manager = PygameAudioManager(FakePygame(mixer))

    manager.consume(
        (
            _event(EventType.FRUIT_DROPPED),
            _event(EventType.FRUIT_MERGED, fruit_id="apple"),
            _event(EventType.DANGER_CHANGED, active=True),
            _event(EventType.FRUIT_MERGED, fruit_id="watermelon"),
            _event(EventType.ROUND_ENDED),
        )
    )

    assert [name for _, name in mixer.played] == ["result"]
    assert mixer.channels[14].stop_count == 1
    manager.close()


def test_warning_and_watermelon_outrank_merge_and_drop() -> None:
    mixer = FakeMixer(initialized=True)
    manager = PygameAudioManager(FakePygame(mixer))

    manager.consume(
        (
            _event(EventType.FRUIT_DROPPED),
            _event(EventType.FRUIT_MERGED, fruit_id="apple"),
            _event(EventType.FRUIT_MERGED, double_watermelon=True),
            _event(EventType.DANGER_CHANGED, active=True),
        )
    )

    assert [name for _, name in mixer.played] == [
        "warning",
        "watermelon",
        "merge",
        "drop",
    ]
    manager.close()


def test_drop_limit_and_warning_repeat_limit_use_injected_clock() -> None:
    mixer = FakeMixer(initialized=True)
    now = [20.0]
    manager = PygameAudioManager(FakePygame(mixer), clock=lambda: now[0])

    manager.consume(tuple(_event(EventType.FRUIT_DROPPED) for _ in range(10)))
    assert sum(name == "drop" for _, name in mixer.played) == 8

    manager.consume((_event(EventType.DANGER_CHANGED, active=True),))
    manager.consume((_event(EventType.DANGER_CHANGED, active=True),))
    assert sum(name == "warning" for _, name in mixer.played) == 1
    now[0] += 1.0
    manager.consume((_event(EventType.DANGER_CHANGED, active=True),))
    assert sum(name == "warning" for _, name in mixer.played) == 2
    manager.close()


def test_score_updates_and_inactive_danger_are_silent() -> None:
    mixer = FakeMixer(initialized=True)
    manager = PygameAudioManager(FakePygame(mixer))

    manager.consume(
        (
            _event(EventType.SCORE_CHANGED),
            _event(EventType.DANGER_CHANGED, active=False),
        )
    )

    assert mixer.played == []
    manager.close()


def test_pause_resume_and_close_release_owned_mixer() -> None:
    mixer = FakeMixer()
    manager = PygameAudioManager(FakePygame(mixer))
    manager.pause()
    assert all(channel.paused for channel in mixer.channels)

    manager.consume((_event(EventType.FRUIT_DROPPED),))
    assert mixer.played == []
    manager.resume()
    assert all(not channel.paused for channel in mixer.channels)
    manager.consume((_event(EventType.FRUIT_DROPPED),))
    assert mixer.played == [(0, "drop")]

    manager.close()
    manager.close()
    assert mixer.quit_count == 1
    assert all(channel.stop_count >= 1 for channel in mixer.channels)
    assert not manager.available


def test_manager_does_not_quit_a_mixer_initialized_by_its_caller() -> None:
    mixer = FakeMixer(initialized=True)
    manager = PygameAudioManager(FakePygame(mixer))

    manager.close()

    assert mixer.quit_count == 0


def test_missing_device_returns_a_no_op_manager_and_keeps_contract_methods_safe() -> None:
    manager = create_audio_manager(FakePygame(FakeMixer(fail_init=True)))

    assert isinstance(manager, NullAudioManager)
    assert manager.failure_reason == "audio device unavailable"
    manager.consume((_event(EventType.FRUIT_DROPPED),))
    manager.set_gains(master=0.0, effects=0.0, music=0.0)
    manager.pause()
    manager.resume()
    manager.close()


@pytest.mark.parametrize("gain", [-0.1, 1.1, float("nan")])
def test_gain_validation_rejects_values_outside_the_contract(gain: float) -> None:
    mixer = FakeMixer(initialized=True)
    manager = PygameAudioManager(FakePygame(mixer))

    with pytest.raises(ValueError, match="gain"):
        manager.set_gains(master=gain, effects=0.5, music=0.5)
    manager.close()
