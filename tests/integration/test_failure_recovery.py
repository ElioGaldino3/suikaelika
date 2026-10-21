"""Integration checks for invalid/unavailable local services and the game flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from suika_elika.audio import NullAudioManager
from suika_elika.contracts import InputAction, InputEdge, InputFrame, RoundState
from suika_elika.game.physics import PhysicsWorld
from suika_elika.game.session import GameSession
from suika_elika.input.manager import InputManager
from suika_elika.persistence import JsonPersistence
from suika_elika.platform import UserPaths
from suika_elika.scene_manager import SceneManager


def _start_and_drop(persistence: JsonPersistence) -> tuple[GameSession, NullAudioManager]:
    session = GameSession(PhysicsWorld(), persistence=persistence, seed=38)
    audio = NullAudioManager("audio device unavailable")
    manager = SceneManager(session, persistence, InputManager(), audio)
    manager.handle_actions(InputFrame(edges=(InputEdge(0, InputAction.CONFIRM),)))
    assert manager.current_name == "play"

    manager.handle_actions(InputFrame(edges=(InputEdge(1, InputAction.DROP),)))
    events = manager.simulation_step()
    assert session.drop_count == 1
    assert session.round_state is RoundState.PLAYING
    audio.consume(events)
    return session, audio


def test_corrupt_saved_json_and_missing_audio_do_not_block_a_classic_drop(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config"
    data = tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "controllers.json").write_text("{bad", encoding="utf-8")
    (data / "records.json").write_text("{bad", encoding="utf-8")
    (data / "statistics.json").write_text("[]", encoding="utf-8")
    persistence = JsonPersistence(
        UserPaths(config_dir=config, data_dir=data, log_dir=tmp_path / "logs")
    )

    session, audio = _start_and_drop(persistence)

    assert session.snapshot.current_fruit is not None
    assert session.snapshot.next_fruit is not None
    assert not audio.available
    assert list(config.glob("controllers.json.recovery-*"))
    assert list(data.glob("records.json.recovery-*"))
    assert list(data.glob("statistics.json.recovery-*"))


@pytest.mark.parametrize("blocked_dir", ["config", "data"])
def test_unwritable_persistence_directories_do_not_block_a_classic_drop(
    tmp_path: Path,
    blocked_dir: str,
) -> None:
    config_path = tmp_path / "config-file"
    data_path = tmp_path / "data-file"
    log_path = tmp_path / "logs-file"
    for path in (config_path, data_path, log_path):
        path.write_text("not a directory", encoding="utf-8")
    if blocked_dir == "config":
        config = config_path
        data = tmp_path / "usable-data"
    else:
        config = tmp_path / "usable-config"
        data = data_path
    persistence = JsonPersistence(
        UserPaths(config_dir=config, data_dir=data, log_dir=log_path)
    )

    session, audio = _start_and_drop(persistence)

    assert session.drop_count == 1
    assert session.round_state is RoundState.PLAYING
    assert not audio.available
    assert persistence.last_error is not None
