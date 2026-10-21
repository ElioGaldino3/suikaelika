"""Two independent boards, resolved together at each fixed simulation step."""

from __future__ import annotations

from dataclasses import dataclass

from suika_elika.contracts import DomainEvent, InputFrame, RoundState, SessionSnapshot
from suika_elika.game.physics import PhysicsConfig, PhysicsWorld
from suika_elika.game.session import GameSession

BATTLE_WIDTH = 480.0
BATTLE_HEIGHT = 460.0
BATTLE_TARGETS = (1000, 2000, 5000)
BATTLE_TARGET = BATTLE_TARGETS[0]


@dataclass(frozen=True, slots=True)
class BattleSnapshot:
    players: tuple[SessionSnapshot, SessionSnapshot]
    target: int
    finished: bool
    winner: int | None
    reason: str


class BattleSession:
    """Race to the selected target; overflow loses, simultaneous outcomes draw.

    Player numbers are 1 and 2. Overflow takes precedence over scores produced
    in the same tick. Both worlds advance before resolving the outcome, so
    processing order never favors player one. Battle has no classic persistence.
    """

    def __init__(self, *, fixed_dt: float = 1 / 120, seed: int = 0) -> None:
        def board() -> GameSession:
            return GameSession(
                PhysicsWorld(
                    PhysicsConfig(
                        width=BATTLE_WIDTH,
                        height=BATTLE_HEIGHT,
                        fixed_dt=fixed_dt,
                    )
                ),
                width=BATTLE_WIDTH,
                height=BATTLE_HEIGHT,
                fixed_dt=fixed_dt,
                seed=seed,
                mode="battle",
            )

        self.target = BATTLE_TARGET
        self.players = (board(), board())
        self.finished = False
        self.winner: int | None = None
        self.reason = ""

    @property
    def snapshot(self) -> BattleSnapshot:
        return BattleSnapshot(
            (self.players[0].snapshot, self.players[1].snapshot),
            self.target,
            self.finished,
            self.winner,
            self.reason,
        )

    def restart(self, *, target: int | None = None) -> None:
        if target is not None:
            if type(target) is not int or target not in BATTLE_TARGETS:
                raise ValueError("battle target must be 1000, 2000 or 5000")
            self.target = target
        for player in self.players:
            player.restart()
        self.finished = False
        self.winner = None
        self.reason = ""

    def pause(self) -> None:
        for player in self.players:
            player.pause()

    def resume(self) -> None:
        if not self.finished:
            for player in self.players:
                player.resume()

    def step(self, frames: tuple[InputFrame, InputFrame]) -> tuple[DomainEvent, ...]:
        if self.finished or any(p.round_state is RoundState.PAUSED for p in self.players):
            return ()
        events = self.players[0].step(frames[0]) + self.players[1].step(frames[1])
        lost = tuple(p.round_state is RoundState.GAME_OVER for p in self.players)
        reached = tuple(p.score >= self.target for p in self.players)
        if any(lost):
            self.finished = True
            self.winner = None if all(lost) else (2 if lost[0] else 1)
            self.reason = "overflow"
        elif any(reached):
            self.finished = True
            self.winner = None if all(reached) else (1 if reached[0] else 2)
            self.reason = "target"
        if self.finished:
            self.pause()
        return events
