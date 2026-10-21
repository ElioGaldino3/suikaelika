from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from suika_elika.game.catalog import catalog_from_data, load_catalog


def test_classic_catalog_matches_all_proposed_fruit_rules() -> None:
    catalog = load_catalog()

    assert catalog.ruleset_version == "classic-v5"
    assert len(catalog.entries) == 11
    assert [entry.fruit_id for entry in catalog.entries] == [
        "cherry",
        "strawberry",
        "grape",
        "lemon",
        "apple",
        "orange",
        "pear",
        "peach",
        "pineapple",
        "melon",
        "watermelon",
    ]
    assert [entry.definition.radius for entry in catalog.entries] == [
        14,
        19,
        24,
        30,
        36,
        43,
        51,
        61,
        73,
        88,
        106,
    ]
    assert [entry.definition.points_on_spawn for entry in catalog.entries] == [
        0,
        1,
        3,
        6,
        10,
        15,
        21,
        28,
        36,
        45,
        55,
    ]
    assert [entry.color for entry in catalog.entries] == [
        "#D92D59",
        "#F34B58",
        "#9454C4",
        "#F4D54A",
        "#E95B45",
        "#F59B32",
        "#A3CE4B",
        "#F6A0A1",
        "#E9AE39",
        "#C8DA76",
        "#49A75F",
    ]
    assert catalog.get("watermelon").level == 11
    assert [fruit.level for fruit in catalog.launch_definitions] == [1, 2, 3, 4, 5]
    assert catalog.launch_weight_values == (30, 25, 20, 15, 10)
    assert sum(catalog.launch_weight_values) == 100


def test_catalog_uses_proposed_mass_from_radius_area() -> None:
    catalog = load_catalog()

    for entry in catalog.entries:
        assert entry.definition.mass == pytest.approx((entry.definition.radius / 14) ** 2)


def test_hitbox_scales_change_physics_radii_and_isolate_the_ruleset() -> None:
    catalog = load_catalog()
    adjusted = catalog.with_hitbox_scales((("apple", 1.25),))

    assert catalog.get("apple").definition.radius == 36
    assert adjusted.get("apple").definition.radius == pytest.approx(45)
    assert adjusted.get("cherry").definition.radius == 14
    assert adjusted.ruleset_version.startswith("classic-v5-hitbox-")
    assert adjusted.ruleset_version != catalog.ruleset_version
    assert catalog.with_hitbox_scales((("apple", 1.0),)) is catalog

    with pytest.raises(ValueError, match="unknown fruit ids"):
        catalog.with_hitbox_scales((("unknown", 1.1),))


def test_catalog_loader_accepts_an_explicit_rules_file(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "data" / "rules" / "classic-v3.json"
    target = tmp_path / "alternate.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert load_catalog(target).ruleset_version == "classic-v3"


def read_rules() -> dict[str, object]:
    path = Path(__file__).parents[2] / "data" / "rules" / "classic-v3.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.update(ruleset_version=""), "ruleset_version"),
        (lambda data: data["fruits"].pop(), "catalog must contain"),
        (lambda data: data["fruits"][1].update(id="cherry"), "fruit ids must be unique"),
        (lambda data: data["fruits"][1].update(level=1), "ordered consecutively"),
        (lambda data: data["fruits"][0].update(radius=True), "radius must be a number"),
        (lambda data: data["fruits"][0].update(color="red"), "#RRGGBB"),
        (lambda data: data["spawn_weights"][0].update(weight=0), "positive integers"),
        (lambda data: data["spawn_weights"][0].update(fruit_id="watermelon"), "levels 1 through 5"),
        (lambda data: data["spawn_weights"][0].update(weight=29), "sum to 100"),
    ],
)
def test_catalog_validation_rejects_invalid_rules(mutate: object, message: str) -> None:
    data = copy.deepcopy(read_rules())
    mutate(data)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        catalog_from_data(data)


def test_catalog_loader_reports_invalid_json_file(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="could not load ruleset"):
        load_catalog(path)
