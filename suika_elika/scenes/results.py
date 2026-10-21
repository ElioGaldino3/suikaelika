"""Immutable results summary and post-round navigation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from suika_elika.contracts import SessionSnapshot

from .title import MenuItem, MenuScene


@dataclass(frozen=True, slots=True)
class ResultSummary:
    score: int
    high_score: int
    best_fruit_level: int
    watermelons: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (
                self.score,
                self.high_score,
                self.best_fruit_level,
                self.watermelons,
            )
        ):
            raise ValueError("result counters must be non-negative integers")
        if not isfinite(self.duration_seconds) or self.duration_seconds < 0:
            raise ValueError("result duration must be finite and non-negative")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: SessionSnapshot,
        *,
        best_fruit_level: int = 0,
        watermelons: int = 0,
        duration_seconds: float = 0.0,
    ) -> ResultSummary:
        return cls(
            score=snapshot.score,
            high_score=snapshot.high_score,
            best_fruit_level=best_fruit_level,
            watermelons=watermelons,
            duration_seconds=duration_seconds,
        )


class ResultsScene(MenuScene):
    def __init__(self, summary: ResultSummary) -> None:
        super().__init__(
            "Fim de jogo",
            (
                MenuItem("Jogar novamente", "play", (("restart", True),)),
                MenuItem("Menu", "title"),
            ),
            subtitle=(
                f"Pontos: {summary.score} · Recorde: {summary.high_score}\n"
                f"Melhor fruta: nível {summary.best_fruit_level} · "
                f"Melancias: {summary.watermelons}\n"
                f"Duração: {int(summary.duration_seconds // 60):02d}:"
                f"{int(summary.duration_seconds % 60):02d}"
            ),
        )
        self.summary = summary


__all__ = ["ResultSummary", "ResultsScene"]
