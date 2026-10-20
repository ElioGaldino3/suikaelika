"""Seeded fruit sequence isolated from presentation randomness."""

from __future__ import annotations

import random

from suika_elika.contracts import FruitDefinition
from suika_elika.game.catalog import FruitCatalog, load_catalog


class FruitSequence:
    """Own the current and preview fruit for one deterministic game session."""

    __slots__ = ("_catalog", "_random", "_seed", "_current", "_next", "_accepted_drops")

    def __init__(self, seed: int | str | bytes | bytearray, catalog: FruitCatalog | None = None):
        self._catalog = catalog or load_catalog()
        self._seed = seed
        self._random = random.Random(seed)
        self._current = self._draw()
        self._next = self._draw()
        self._accepted_drops = 0

    @property
    def seed(self) -> int | str | bytes | bytearray:
        return self._seed

    @property
    def ruleset_version(self) -> str:
        return self._catalog.ruleset_version

    @property
    def current(self) -> FruitDefinition:
        return self._current

    @property
    def next(self) -> FruitDefinition:
        return self._next

    @property
    def accepted_drops(self) -> int:
        return self._accepted_drops

    def try_consume_drop(self, *, accepted: bool) -> bool:
        """Advance only after an accepted drop; rejected inputs consume no RNG."""
        if not accepted:
            return False
        self._current = self._next
        self._next = self._draw()
        self._accepted_drops += 1
        return True

    def _draw(self) -> FruitDefinition:
        return self._random.choices(
            self._catalog.launch_definitions,
            weights=self._catalog.launch_weight_values,
            k=1,
        )[0]
