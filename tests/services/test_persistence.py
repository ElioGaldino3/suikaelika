from __future__ import annotations

import json
from pathlib import Path

import pytest

from suika_elika.contracts.ports import RecordData, SettingsData
from suika_elika.persistence import (
    SCHEMA_VERSION,
    ControllerProfileData,
    JsonPersistence,
    StatisticsData,
)
from suika_elika.platform import UserPaths


def make_store(root: Path) -> JsonPersistence:
    paths = UserPaths(root / "config", root / "data", root / "logs")
    return JsonPersistence(paths)


def test_versioned_data_round_trips_and_previous_file_is_backed_up(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    settings = SettingsData(
        master_gain=0.4,
        effects_gain=0.6,
        music_gain=0.2,
        effects_reduced=True,
        vibration_enabled=True,
        control_profile_id="arcade",
        fullscreen=False,
        safe_area_fraction=0.08,
        fruit_hitbox_scales=(("apple", 1.25), ("melon", 0.95)),
    )
    profile = ControllerProfileData(
        "arcade",
        "Arcade pad",
        "joystick",
        (("drop", "button:1"), ("pause", "button:7")),
        platform="linux",
        guid="03000000abcd",
        axes=(("move_x", 0), ("move_y", 1)),
        inverted_axes=("move_y",),
        deadzone=0.18,
        sensitivity=1.2,
    )
    store.save_settings(SettingsData())
    store.save_settings(settings)
    store.save_profiles((profile,))
    store.save_record(RecordData("classic-v1", 12, 4, 0, duration_seconds=60.5))
    store.save_record(RecordData("classic-v1", 9, 5, 1, duration_seconds=72.0))
    store.save_record(RecordData("classic-v2", 3, 2, 0, duration_seconds=30.0))
    store.save_record(
        RecordData("classic-v1", 1, 1, 0, mode="arcade", duration_seconds=15.0)
    )
    statistics = StatisticsData(sessions_played=5, merges=28, best_fruit_level=9, watermelons=2)
    store.save_statistics(statistics)

    settings_document = json.loads((tmp_path / "config" / "settings.json").read_text())
    assert settings_document["schema_version"] == SCHEMA_VERSION
    assert settings_document["app_version"]
    assert settings_document["saved_at"].endswith("+00:00")
    assert json.loads((tmp_path / "config" / "settings.json.bak").read_text())["data"][
        "control_profile_id"
    ] == "default"

    reopened = make_store(tmp_path)
    assert reopened.load_settings() == settings
    assert reopened.load_profiles() == (profile,)
    records = {
        (record.mode, record.ruleset_version): record for record in reopened.load_records()
    }
    assert records == {
        ("arcade", "classic-v1"): RecordData(
            "classic-v1", 1, 1, 0, mode="arcade", duration_seconds=15.0
        ),
        ("classic", "classic-v1"): RecordData(
            "classic-v1", 12, 5, 1, duration_seconds=60.5
        ),
        ("classic", "classic-v2"): RecordData(
            "classic-v2", 3, 2, 0, duration_seconds=30.0
        ),
    }
    assert reopened.load_statistics() == statistics


def test_legacy_settings_without_hitbox_scales_use_defaults(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save_settings(SettingsData())
    path = tmp_path / "config" / "settings.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["data"].pop("fruit_hitbox_scales")
    path.write_text(json.dumps(document), encoding="utf-8")

    assert make_store(tmp_path).load_settings() == SettingsData()


def test_corrupt_file_is_preserved_and_defaults_remain_available(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    path = tmp_path / "config" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    invalid = b'{"schema_version":1, broken'
    path.write_bytes(invalid)

    assert store.load_settings() is None
    assert path.read_bytes() == invalid
    recoveries = list(path.parent.glob("settings.json.recovery-*"))
    assert len(recoveries) == 1
    assert recoveries[0].read_bytes() == invalid

    assert store.load_settings() is None
    assert len(list(path.parent.glob("settings.json.recovery-*"))) == 1
    assert "invalid data" in (store.last_error or "")


def test_invalid_schema_and_values_are_preserved(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    path = tmp_path / "data" / "records.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "app_version": "0.1.0",
            "saved_at": "2026-10-20T12:00:00+00:00",
            "data": {"records": [{"ruleset_version": "classic-v1", "score": True,
                                    "best_fruit_level": 3, "watermelons": 0}]},
        }
    ).encode()
    path.write_bytes(original)

    assert store.load_records() == ()
    assert path.read_bytes() == original
    assert list(path.parent.glob("records.json.recovery-*"))[0].read_bytes() == original


def test_write_failure_is_reported_but_keeps_values_available_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path)
    desired = SettingsData(master_gain=0.25)

    def fail_replace(_source: str, _destination: Path) -> None:
        raise PermissionError("simulated disk failure")

    monkeypatch.setattr("suika_elika.persistence.os.replace", fail_replace)
    store.save_settings(desired)

    assert store.last_error == "write failed (PermissionError)"
    assert store.load_settings() == desired
    assert not (tmp_path / "config" / "settings.json").exists()


def test_saves_reject_invalid_values_even_if_model_annotations_were_bypassed(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="gains"):
        store.save_settings(SettingsData(master_gain=True))  # type: ignore[arg-type]
    invalid_record = object.__new__(RecordData)
    object.__setattr__(invalid_record, "ruleset_version", "classic-v1")
    object.__setattr__(invalid_record, "score", True)
    object.__setattr__(invalid_record, "best_fruit_level", 1)
    object.__setattr__(invalid_record, "watermelons", 0)
    object.__setattr__(invalid_record, "mode", "classic")
    object.__setattr__(invalid_record, "duration_seconds", 1.0)
    with pytest.raises(ValueError, match="record fields"):
        store.save_record(invalid_record)
