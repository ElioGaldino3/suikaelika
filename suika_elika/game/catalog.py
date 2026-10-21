"""Validated fruit rules for the classic mode."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from suika_elika.contracts import FruitDefinition

_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\Z")
_EXPECTED_FRUIT_COUNT = 11


@dataclass(frozen=True, slots=True)
class FruitCatalogEntry:
    """A domain definition plus display metadata stored in the rules file."""

    definition: FruitDefinition
    name: str
    color: str

    @property
    def fruit_id(self) -> str:
        return self.definition.fruit_id

    @property
    def level(self) -> int:
        return self.definition.level


@dataclass(frozen=True, slots=True)
class FruitCatalog:
    """Immutable, validated ruleset data and the weighted launch pool."""

    ruleset_version: str
    entries: tuple[FruitCatalogEntry, ...]
    spawn_weights: tuple[tuple[str, int], ...]
    _by_id: Mapping[str, FruitCatalogEntry]

    @classmethod
    def create(
        cls,
        ruleset_version: str,
        entries: tuple[FruitCatalogEntry, ...],
        spawn_weights: tuple[tuple[str, int], ...],
    ) -> FruitCatalog:
        """Validate cross-entry invariants and create an immutable lookup index."""
        if not ruleset_version or not ruleset_version.strip():
            raise ValueError("ruleset_version must not be empty")
        if len(entries) != _EXPECTED_FRUIT_COUNT:
            raise ValueError(f"catalog must contain {_EXPECTED_FRUIT_COUNT} fruits")
        ids = [entry.fruit_id for entry in entries]
        levels = [entry.level for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("fruit ids must be unique")
        if levels != list(range(1, _EXPECTED_FRUIT_COUNT + 1)):
            raise ValueError("fruit levels must be ordered consecutively from 1 to 11")
        if any(not entry.name.strip() for entry in entries):
            raise ValueError("fruit names must not be empty")
        if any(_COLOR_PATTERN.fullmatch(entry.color) is None for entry in entries):
            raise ValueError("fruit colors must use #RRGGBB notation")

        if not spawn_weights:
            raise ValueError("spawn weights must not be empty")
        weight_ids = [fruit_id for fruit_id, _ in spawn_weights]
        if len(weight_ids) != len(set(weight_ids)):
            raise ValueError("spawn fruit ids must be unique")
        definitions = {entry.fruit_id: entry.definition for entry in entries}
        for fruit_id, weight in spawn_weights:
            definition = definitions.get(fruit_id)
            if definition is None:
                raise ValueError(f"spawn weight references unknown fruit {fruit_id!r}")
            if definition.level > 5:
                raise ValueError("only levels 1 through 5 can be selected for launch")
            if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
                raise ValueError("spawn weights must be positive integers")
        if sum(weight for _, weight in spawn_weights) != 100:
            raise ValueError("spawn weights must sum to 100")
        if set(weight_ids) != {entry.fruit_id for entry in entries if entry.level <= 5}:
            raise ValueError("spawn weights must cover each launchable fruit exactly once")

        return cls(
            ruleset_version=ruleset_version,
            entries=entries,
            spawn_weights=spawn_weights,
            _by_id=MappingProxyType(dict(zip(ids, entries, strict=True))),
        )

    def get(self, fruit_id: str) -> FruitCatalogEntry:
        """Return one entry by stable id, raising KeyError when it is unknown."""
        return self._by_id[fruit_id]

    @property
    def launch_definitions(self) -> tuple[FruitDefinition, ...]:
        """Definitions eligible for the next-fruit draw, in ruleset order."""
        by_id = self._by_id
        return tuple(by_id[fruit_id].definition for fruit_id, _ in self.spawn_weights)

    @property
    def launch_weight_values(self) -> tuple[int, ...]:
        return tuple(weight for _, weight in self.spawn_weights)


def _required_string(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _required_integer(record: dict[str, object], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _required_number(record: dict[str, object], field: str) -> float:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def catalog_from_data(data: object) -> FruitCatalog:
    """Parse and validate a decoded JSON value as a ruleset catalog."""
    if not isinstance(data, dict):
        raise ValueError("ruleset root must be an object")
    record = cast(dict[str, object], data)
    ruleset_version = _required_string(record, "ruleset_version")
    raw_fruits = record.get("fruits")
    raw_weights = record.get("spawn_weights")
    if not isinstance(raw_fruits, list) or not isinstance(raw_weights, list):
        raise ValueError("fruits and spawn_weights must be arrays")

    entries: list[FruitCatalogEntry] = []
    for raw_fruit in raw_fruits:
        if not isinstance(raw_fruit, dict):
            raise ValueError("each fruit must be an object")
        fruit = cast(dict[str, object], raw_fruit)
        radius = _required_number(fruit, "radius")
        entries.append(
            FruitCatalogEntry(
                definition=FruitDefinition(
                    fruit_id=_required_string(fruit, "id"),
                    level=_required_integer(fruit, "level"),
                    radius=radius,
                    mass=_required_number(fruit, "mass"),
                    points_on_spawn=_required_integer(fruit, "points_on_spawn"),
                    visual_key=_required_string(fruit, "id"),
                ),
                name=_required_string(fruit, "name"),
                color=_required_string(fruit, "color"),
            )
        )

    weights: list[tuple[str, int]] = []
    for raw_weight in raw_weights:
        if not isinstance(raw_weight, dict):
            raise ValueError("each spawn weight must be an object")
        weight = cast(dict[str, object], raw_weight)
        weights.append(
            (
                _required_string(weight, "fruit_id"),
                _required_integer(weight, "weight"),
            )
        )
    return FruitCatalog.create(ruleset_version, tuple(entries), tuple(weights))


def load_catalog(path: Path | None = None) -> FruitCatalog:
    """Load the default classic rules or another JSON ruleset path."""
    rules_path = path or (
        Path(__file__).resolve().parents[2] / "data" / "rules" / "classic-v5.json"
    )
    try:
        with rules_path.open("r", encoding="utf-8") as rules_file:
            data = json.load(rules_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not load ruleset from {rules_path}") from error
    return catalog_from_data(data)
