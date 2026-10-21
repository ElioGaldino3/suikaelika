"""Small synthesized sound service with a safe silent fallback.

Importing this module never imports Pygame or opens an audio device. Construct
an audio manager after application startup, then pass copied domain events to
``consume``. The prototype intentionally has no music track yet.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from io import BytesIO
from math import isfinite, pi, sin
from struct import pack
from time import monotonic
from typing import Any
from wave import open as open_wave

from suika_elika.contracts.events import DomainEvent, EventType

_SAMPLE_RATE = 44_100
_CHANNEL_COUNT = 16
_DROP_LIMIT = 8
_DROP_WINDOW_SECONDS = 1.0
_WARNING_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class _SoundCue:
    name: str
    priority: int
    frequency: float
    duration: float
    chord: tuple[float, ...] = ()


_DROP = _SoundCue("drop", 0, 330.0, 0.075)
_MERGE = _SoundCue("merge", 1, 520.0, 0.16, (780.0,))
_WATERMELON = _SoundCue("watermelon", 2, 440.0, 0.62, (554.37, 659.25))
_WARNING = _SoundCue("warning", 3, 880.0, 0.12)
_RESULT = _SoundCue("result", 4, 440.0, 0.68, (349.23, 261.63))


def _validate_gain(value: float, name: str) -> float:
    if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} gain must be finite and between 0 and 1")
    return float(value)


def _tone_wave(cue: _SoundCue, sample_rate: int = _SAMPLE_RATE) -> BytesIO:
    """Build a short original PCM WAV effect using only the Python standard library."""
    frame_count = max(1, round(sample_rate * cue.duration))
    frequencies = (cue.frequency, *cue.chord)
    frames = bytearray()
    for index in range(frame_count):
        position = index / sample_rate
        envelope = min(1.0, index / max(1.0, sample_rate * 0.008))
        envelope *= max(0.0, 1.0 - index / frame_count) ** 1.7
        sample = sum(sin(2 * pi * frequency * position) for frequency in frequencies)
        sample *= envelope * 0.14 / len(frequencies)
        pcm = max(-32768, min(32767, round(sample * 32767)))
        frames.extend(pack("<hh", pcm, pcm))

    output = BytesIO()
    with open_wave(output, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    output.seek(0)
    return output


class NullAudioManager:
    """AudioPort implementation that stores gains but performs no device I/O."""

    __slots__ = ("failure_reason", "_gains", "_closed")

    def __init__(self, failure_reason: str | None = None) -> None:
        self.failure_reason = failure_reason
        self._gains = (0.8, 0.75, 0.35)
        self._closed = False

    @property
    def available(self) -> bool:
        return False

    @property
    def gains(self) -> tuple[float, float, float]:
        return self._gains

    def consume(self, events: tuple[DomainEvent, ...]) -> None:
        del events

    def set_gains(self, *, master: float, effects: float, music: float) -> None:
        self._gains = (
            _validate_gain(master, "master"),
            _validate_gain(effects, "effects"),
            _validate_gain(music, "music"),
        )

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def close(self) -> None:
        self._closed = True


class PygameAudioManager:
    """Pygame mixer adapter for short original PCM effects.

    ``pygame_module`` and ``clock`` are injectable so tests can exercise mixer
    policy without opening a physical audio device.
    """

    __slots__ = (
        "_pygame",
        "_owns_mixer",
        "_channels",
        "_sounds",
        "_clock",
        "_gains",
        "_drop_times",
        "_last_warning_at",
        "_paused",
        "_closed",
        "_available",
        "last_error",
    )

    def __init__(
        self,
        pygame_module: Any | None = None,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        pygame = pygame_module if pygame_module is not None else import_module("pygame")
        mixer = pygame.mixer
        self._pygame = pygame
        self._clock = clock
        self._owns_mixer = mixer.get_init() is None
        self._channels: tuple[Any, ...] = ()
        self._sounds: dict[str, Any] = {}
        self._gains = (0.8, 0.75, 0.35)
        self._drop_times: deque[float] = deque()
        self._last_warning_at = float("-inf")
        self._paused = False
        self._closed = False
        self._available = False
        self.last_error: str | None = None

        try:
            if self._owns_mixer:
                mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=2, buffer=512)
            if mixer.get_init() is None:
                raise RuntimeError("Pygame mixer did not initialize")
            mixer.set_num_channels(_CHANNEL_COUNT)
            self._channels = tuple(mixer.Channel(index) for index in range(_CHANNEL_COUNT))
            self._sounds = {
                cue.name: mixer.Sound(file=_tone_wave(cue))
                for cue in (_DROP, _MERGE, _WATERMELON, _WARNING, _RESULT)
            }
            self._available = True
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            self._stop_channels()
            if self._owns_mixer:
                self._safe_mixer_quit()

    @property
    def available(self) -> bool:
        return self._available and not self._closed

    @property
    def gains(self) -> tuple[float, float, float]:
        return self._gains

    def consume(self, events: tuple[DomainEvent, ...]) -> None:
        if not self.available or self._paused or not events:
            return

        result = next(
            (event for event in events if event.event_type is EventType.ROUND_ENDED),
            None,
        )
        selected_events = (result,) if result is not None else events
        cues = [cue for event in selected_events if (cue := self._cue_for(event)) is not None]
        cues.sort(key=lambda cue: cue.priority, reverse=True)
        now = self._clock()
        self._expire_drop_times(now)

        for cue in cues:
            if cue is _DROP:
                if len(self._drop_times) >= _DROP_LIMIT:
                    continue
                self._drop_times.append(now)
            elif cue is _WARNING:
                if now - self._last_warning_at < _WARNING_INTERVAL_SECONDS:
                    continue
                self._last_warning_at = now
            self._play(cue)

    def set_gains(self, *, master: float, effects: float, music: float) -> None:
        self._gains = (
            _validate_gain(master, "master"),
            _validate_gain(effects, "effects"),
            _validate_gain(music, "music"),
        )
        effect_gain = self._gains[0] * self._gains[1]
        for channel in self._channels:
            try:
                channel.set_volume(effect_gain)
            except Exception as error:
                self.last_error = str(error) or type(error).__name__
                self._disable()
                break

    def pause(self) -> None:
        if not self.available or self._paused:
            return
        try:
            for channel in self._channels:
                channel.pause()
            self._paused = True
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            self._disable()

    def resume(self) -> None:
        if not self.available or not self._paused:
            return
        try:
            for channel in self._channels:
                channel.unpause()
            self._paused = False
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            self._disable()

    def close(self) -> None:
        if self._closed:
            return
        self._stop_channels()
        if self._owns_mixer:
            self._safe_mixer_quit()
        self._closed = True
        self._available = False
        self._sounds.clear()

    def _cue_for(self, event: DomainEvent) -> _SoundCue | None:
        if event.event_type is EventType.FRUIT_DROPPED:
            return _DROP
        if event.event_type is EventType.FRUIT_MERGED:
            payload = dict(event.payload)
            fruit_id = payload.get("fruit_id")
            double_watermelon = payload.get("double_watermelon") is True
            level = payload.get("fruit_level")
            if double_watermelon or fruit_id == "watermelon" or level == 10:
                return _WATERMELON
            return _MERGE
        if event.event_type is EventType.DANGER_CHANGED:
            payload = dict(event.payload)
            if payload.get("active") is False or payload.get("warning") is False:
                return None
            return _WARNING
        if event.event_type is EventType.ROUND_ENDED:
            return _RESULT
        return None

    def _play(self, cue: _SoundCue) -> None:
        if cue is _DROP:
            pool = self._channels[0:8]
        elif cue in (_MERGE, _WATERMELON):
            pool = self._channels[8:14]
        else:
            pool = self._channels[14:16]

        try:
            if cue is _RESULT:
                # A result outranks a warning already using the two reserved channels.
                for channel in pool:
                    channel.stop()
            channel = next((candidate for candidate in pool if not candidate.get_busy()), None)
            if channel is None:
                return
            channel.set_volume(self._gains[0] * self._gains[1])
            channel.play(self._sounds[cue.name])
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            self._disable()

    def _expire_drop_times(self, now: float) -> None:
        while self._drop_times and now - self._drop_times[0] >= _DROP_WINDOW_SECONDS:
            self._drop_times.popleft()

    def _disable(self) -> None:
        self._stop_channels()
        if self._owns_mixer:
            self._safe_mixer_quit()
        self._available = False

    def _stop_channels(self) -> None:
        for channel in self._channels:
            try:
                channel.stop()
            except Exception:
                pass

    def _safe_mixer_quit(self) -> None:
        try:
            self._pygame.mixer.quit()
        except Exception:
            pass


def create_audio_manager(pygame_module: Any | None = None) -> PygameAudioManager | NullAudioManager:
    """Return a live mixer service or a no-op adapter when audio is unavailable."""
    try:
        manager = PygameAudioManager(pygame_module)
    except Exception as error:
        return NullAudioManager(str(error) or type(error).__name__)
    if not manager.available:
        return NullAudioManager(manager.last_error)
    return manager


__all__ = ["NullAudioManager", "PygameAudioManager", "create_audio_manager"]
