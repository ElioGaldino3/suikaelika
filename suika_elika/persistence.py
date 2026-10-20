"""Versioned JSON persistence with atomic replacement and recoverable failures."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .contracts.ports import (
    ControllerProfileData,
    PersistencePort,
    RecordData,
    SettingsData,
    StatisticsData,
)
from .platform import UserPaths, resolve_user_paths

SCHEMA_VERSION = 2


class JsonPersistence(PersistencePort):
    """JSON store for settings, profiles, ruleset records, and statistics.

    Save failures are retained as ``last_error`` and do not raise into gameplay.
    Values remain cached in memory so the caller can continue the current session.
    """

    def __init__(self, paths: UserPaths | None = None) -> None:
        self.paths = paths or resolve_user_paths()
        self.last_error: str | None = None
        self._settings: SettingsData | None = None
        self._profiles: tuple[ControllerProfileData, ...] | None = None
        self._records: tuple[RecordData, ...] | None = None
        self._statistics: StatisticsData | None = None
        self._recovery_attempted: set[Path] = set()
        failed_dirs = self.paths.create_directories()
        if failed_dirs:
            self.last_error = "directory creation failed"

    def load_settings(self) -> SettingsData | None:
        if self._settings is not None:
            return self._settings
        data = self._read_data(self.paths.config_dir / "settings.json")
        if data is None:
            return None
        try:
            if set(data) != {
                "master_gain",
                "effects_gain",
                "music_gain",
                "effects_reduced",
                "vibration_enabled",
                "control_profile_id",
                "fullscreen",
                "safe_area_fraction",
            }:
                raise ValueError("settings fields do not match the schema")
            gains = (data["master_gain"], data["effects_gain"], data["music_gain"])
            if any(type(gain) not in (int, float) or not math.isfinite(gain) for gain in gains):
                raise ValueError("settings gains must be finite numbers")
            safe_area = data["safe_area_fraction"]
            if type(safe_area) not in (int, float) or not math.isfinite(safe_area):
                raise ValueError("safe area must be a finite number")
            if (
                type(data["effects_reduced"]) is not bool
                or type(data["vibration_enabled"]) is not bool
                or type(data["fullscreen"]) is not bool
            ):
                raise ValueError("settings flags must be booleans")
            if not isinstance(data["control_profile_id"], str):
                raise ValueError("control profile id must be text")
            self._settings = SettingsData(
                master_gain=float(data["master_gain"]),
                effects_gain=float(data["effects_gain"]),
                music_gain=float(data["music_gain"]),
                effects_reduced=data["effects_reduced"],
                vibration_enabled=data["vibration_enabled"],
                control_profile_id=data["control_profile_id"],
                fullscreen=data["fullscreen"],
                safe_area_fraction=float(safe_area),
            )
            return self._settings
        except (TypeError, ValueError, KeyError) as error:
            self._preserve_invalid(self.paths.config_dir / "settings.json", error)
            return None

    def save_settings(self, settings: SettingsData) -> None:
        if not isinstance(settings, SettingsData):
            raise TypeError("settings must be SettingsData")
        gains = (settings.master_gain, settings.effects_gain, settings.music_gain)
        if any(
            type(gain) not in (int, float)
            or not math.isfinite(gain)
            or not 0 <= gain <= 1
            for gain in gains
        ):
            raise ValueError("settings gains must be finite numbers between 0 and 1")
        if (
            type(settings.effects_reduced) is not bool
            or type(settings.vibration_enabled) is not bool
            or type(settings.fullscreen) is not bool
            or not isinstance(settings.control_profile_id, str)
            or not settings.control_profile_id
            or type(settings.safe_area_fraction) not in (int, float)
            or not math.isfinite(settings.safe_area_fraction)
            or not 0 <= settings.safe_area_fraction <= 0.25
        ):
            raise ValueError("settings flags and control profile id are invalid")
        self._settings = settings
        self._write_data(
            self.paths.config_dir / "settings.json",
            {
                "master_gain": settings.master_gain,
                "effects_gain": settings.effects_gain,
                "music_gain": settings.music_gain,
                "effects_reduced": settings.effects_reduced,
                "vibration_enabled": settings.vibration_enabled,
                "control_profile_id": settings.control_profile_id,
                "fullscreen": settings.fullscreen,
                "safe_area_fraction": settings.safe_area_fraction,
            },
        )

    def load_profiles(self) -> tuple[ControllerProfileData, ...]:
        if self._profiles is not None:
            return self._profiles
        data = self._read_data(self.paths.config_dir / "controllers.json")
        if data is None:
            return ()
        try:
            if set(data) != {"profiles"} or not isinstance(data["profiles"], list):
                raise ValueError("controller profile data does not match the schema")
            profiles = tuple(self._profile_from_json(item) for item in data["profiles"])
            ids = [profile.profile_id for profile in profiles]
            if len(ids) != len(set(ids)):
                raise ValueError("controller profile ids must be unique")
            self._profiles = profiles
            return profiles
        except (TypeError, ValueError, KeyError) as error:
            self._preserve_invalid(self.paths.config_dir / "controllers.json", error)
            self._profiles = ()
            return ()

    def save_profiles(self, profiles: tuple[ControllerProfileData, ...]) -> None:
        if not isinstance(profiles, tuple) or any(
            not isinstance(profile, ControllerProfileData) for profile in profiles
        ):
            raise TypeError("profiles must be a tuple of ControllerProfileData")
        if len({profile.profile_id for profile in profiles}) != len(profiles):
            raise ValueError("controller profile ids must be unique")
        self._profiles = profiles
        self._write_data(
            self.paths.config_dir / "controllers.json",
            {"profiles": [self._profile_to_json(profile) for profile in profiles]},
        )

    def load_records(self) -> tuple[RecordData, ...]:
        if self._records is not None:
            return self._records
        data = self._read_data(self.paths.data_dir / "records.json")
        if data is None:
            return ()
        try:
            if set(data) != {"records"} or not isinstance(data["records"], list):
                raise ValueError("record data does not match the schema")
            records = tuple(self._record_from_json(item) for item in data["records"])
            keys = [(record.mode, record.ruleset_version) for record in records]
            if len(keys) != len(set(keys)):
                raise ValueError("mode and ruleset pairs must be unique")
            self._records = records
            return records
        except (TypeError, ValueError, KeyError) as error:
            self._preserve_invalid(self.paths.data_dir / "records.json", error)
            self._records = ()
            return ()

    def save_record(self, record: RecordData) -> None:
        if not isinstance(record, RecordData):
            raise TypeError("record must be RecordData")
        if (
            not isinstance(record.ruleset_version, str)
            or not record.ruleset_version
                or not record.mode
            or any(
                type(value) is not int or value < 0
                for value in (record.score, record.best_fruit_level, record.watermelons)
            )
                or type(record.duration_seconds) not in (int, float)
                or not math.isfinite(record.duration_seconds)
                or record.duration_seconds < 0
        ):
            raise ValueError("record fields are invalid")
        records = {(item.mode, item.ruleset_version): item for item in self.load_records()}
        key = (record.mode, record.ruleset_version)
        previous = records.get(key)
        if previous is not None:
            best_score_record = record if record.score > previous.score else previous
            record = RecordData(
                ruleset_version=record.ruleset_version,
                score=max(previous.score, record.score),
                best_fruit_level=max(previous.best_fruit_level, record.best_fruit_level),
                watermelons=max(previous.watermelons, record.watermelons),
                mode=record.mode,
                duration_seconds=best_score_record.duration_seconds,
            )
        records[key] = record
        self._records = tuple(records[item_key] for item_key in sorted(records))
        self._write_data(
            self.paths.data_dir / "records.json",
            {"records": [self._record_to_json(item) for item in self._records]},
        )

    def load_statistics(self) -> StatisticsData:
        if self._statistics is not None:
            return self._statistics
        data = self._read_data(self.paths.data_dir / "statistics.json")
        if data is None:
            self._statistics = StatisticsData()
            return self._statistics
        try:
            expected = {"sessions_played", "merges", "best_fruit_level", "watermelons"}
            if set(data) != expected:
                raise ValueError("statistics fields do not match the schema")
            self._statistics = StatisticsData(**data)
            return self._statistics
        except (TypeError, ValueError, KeyError) as error:
            self._preserve_invalid(self.paths.data_dir / "statistics.json", error)
            self._statistics = StatisticsData()
            return self._statistics

    def save_statistics(self, statistics: StatisticsData) -> None:
        if not isinstance(statistics, StatisticsData):
            raise TypeError("statistics must be StatisticsData")
        self._statistics = statistics
        self._write_data(
            self.paths.data_dir / "statistics.json",
            {
                "sessions_played": statistics.sessions_played,
                "merges": statistics.merges,
                "best_fruit_level": statistics.best_fruit_level,
                "watermelons": statistics.watermelons,
            },
        )

    def _read_data(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError, UnicodeError) as error:
            self._preserve_invalid(path, error)
            return None
        if not isinstance(raw, dict):
            self._preserve_invalid(path, ValueError("document root must be an object"))
            return None
        if not isinstance(raw.get("app_version"), str) or not isinstance(raw.get("saved_at"), str):
            self._preserve_invalid(path, ValueError("document metadata is missing"))
            return None
        try:
            datetime.fromisoformat(raw["saved_at"])
        except ValueError as error:
            self._preserve_invalid(path, error)
            return None
        if type(raw.get("schema_version")) is not int or raw["schema_version"] != SCHEMA_VERSION:
            self._preserve_invalid(path, ValueError("unsupported schema version"))
            return None
        data = raw.get("data")
        if not isinstance(data, dict):
            self._preserve_invalid(path, ValueError("document data must be an object"))
            return None
        return data

    def _write_data(self, path: Path, data: dict[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "app_version": __version__,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        content = json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as file:
                temporary = file.name
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            if path.exists():
                backup = path.with_name(f"{path.name}.bak")
                shutil.copy2(path, backup)
            os.replace(temporary, path)
            temporary = None
            self.last_error = None
        except OSError as error:
            self.last_error = f"write failed ({type(error).__name__})"
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def _preserve_invalid(self, path: Path, error: Exception) -> None:
        self.last_error = f"invalid data ({type(error).__name__})"
        if path in self._recovery_attempted:
            return
        self._recovery_attempted.add(path)
        if not path.is_file():
            return
        recovery = path.with_name(f"{path.name}.recovery-{time.time_ns()}")
        try:
            shutil.copy2(path, recovery)
        except OSError:
            # The source file remains untouched even when the recovery copy fails.
            pass

    @staticmethod
    def _profile_to_json(profile: ControllerProfileData) -> dict[str, Any]:
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "backend": profile.backend,
            "bindings": [list(binding) for binding in profile.bindings],
            "platform": profile.platform,
            "guid": profile.guid,
            "axes": [list(axis) for axis in profile.axes],
            "inverted_axes": list(profile.inverted_axes),
            "deadzone": profile.deadzone,
            "sensitivity": profile.sensitivity,
        }

    @staticmethod
    def _profile_from_json(data: Any) -> ControllerProfileData:
        if not isinstance(data, dict) or set(data) != {
            "profile_id",
            "name",
            "backend",
            "bindings",
            "platform",
            "guid",
            "axes",
            "inverted_axes",
            "deadzone",
            "sensitivity",
        }:
            raise ValueError("profile fields do not match the schema")
        bindings = data["bindings"]
        if not isinstance(bindings, list):
            raise ValueError("profile bindings must be a list")
        if any(not isinstance(binding, list) or len(binding) != 2 for binding in bindings):
            raise ValueError("each controller binding must contain two values")
        axes = data["axes"]
        inverted_axes = data["inverted_axes"]
        if not isinstance(axes, list) or not isinstance(inverted_axes, list):
            raise ValueError("profile axes and inversions must be lists")
        if any(not isinstance(axis, list) or len(axis) != 2 for axis in axes):
            raise ValueError("each controller axis must contain a name and index")
        if any(not isinstance(name, str) for name in inverted_axes):
            raise ValueError("inverted axis names must be text")
        if type(data["deadzone"]) not in (int, float) or type(data["sensitivity"]) not in (
            int,
            float,
        ):
            raise ValueError("profile calibration values must be numeric")
        return ControllerProfileData(
            profile_id=data["profile_id"],
            name=data["name"],
            backend=data["backend"],
            bindings=tuple(tuple(binding) for binding in bindings),
            platform=data["platform"],
            guid=data["guid"],
            axes=tuple(tuple(axis) for axis in axes),
            inverted_axes=tuple(inverted_axes),
            deadzone=float(data["deadzone"]),
            sensitivity=float(data["sensitivity"]),
        )

    @staticmethod
    def _record_to_json(record: RecordData) -> dict[str, Any]:
        return {
            "mode": record.mode,
            "ruleset_version": record.ruleset_version,
            "score": record.score,
            "best_fruit_level": record.best_fruit_level,
            "watermelons": record.watermelons,
            "duration_seconds": record.duration_seconds,
        }

    @staticmethod
    def _record_from_json(data: Any) -> RecordData:
        if not isinstance(data, dict) or set(data) != {
            "ruleset_version",
            "score",
            "best_fruit_level",
            "watermelons",
            "mode",
            "duration_seconds",
        }:
            raise ValueError("record fields do not match the schema")
        if any(
            type(data[key]) is not int
            for key in ("score", "best_fruit_level", "watermelons")
        ):
            raise ValueError("record counters must be integers")
        if not isinstance(data["ruleset_version"], str) or not isinstance(data["mode"], str):
            raise ValueError("record mode and ruleset version must be text")
        if type(data["duration_seconds"]) not in (int, float) or not math.isfinite(
            data["duration_seconds"]
        ):
            raise ValueError("record duration must be a finite number")
        return RecordData(
            ruleset_version=data["ruleset_version"],
            score=data["score"],
            best_fruit_level=data["best_fruit_level"],
            watermelons=data["watermelons"],
            mode=data["mode"],
            duration_seconds=float(data["duration_seconds"]),
        )


__all__ = [
    "ControllerProfileData",
    "JsonPersistence",
    "PersistencePort",
    "RecordData",
    "SCHEMA_VERSION",
    "SettingsData",
    "StatisticsData",
]
