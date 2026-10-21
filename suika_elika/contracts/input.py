"""Semantic input values and exactly-once simulation edge consumption."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import isfinite


class InputAction(str, Enum):
    DROP = "drop"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    PAUSE = "pause"
    NAV_UP = "nav_up"
    NAV_DOWN = "nav_down"


@dataclass(frozen=True, slots=True)
class InputEdge:
    """A rising edge with a globally increasing sequence number."""

    sequence: int
    action: InputAction

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("input sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class InputFrame:
    """Per-render-frame semantic input, with no SDL/device references.

    ``move_y`` is the normalized vertical axis used by menu navigation. Discrete
    navigation actions are emitted as edges by the input manager's UI-time
    threshold, hysteresis, and repeat logic.
    """

    move_x: float = 0.0
    fine_adjust: bool = False
    edges: tuple[InputEdge, ...] = ()
    move_y: float = 0.0
    drop_held: bool = False

    def __post_init__(self) -> None:
        if type(self.drop_held) is not bool:
            raise TypeError("drop_held must be a boolean")
        if not isfinite(self.move_x) or not -1.0 <= self.move_x <= 1.0:
            raise ValueError("move_x must be finite and normalized to [-1, 1]")
        if not isfinite(self.move_y) or not -1.0 <= self.move_y <= 1.0:
            raise ValueError("move_y must be finite and normalized to [-1, 1]")
        if not isinstance(self.edges, tuple):
            raise TypeError("edges must be an immutable tuple")
        if any(not isinstance(edge, InputEdge) for edge in self.edges):
            raise TypeError("edges must contain InputEdge values")
        sequences = [edge.sequence for edge in self.edges]
        if len(sequences) != len(set(sequences)):
            raise ValueError("edge sequence numbers must be unique within a frame")
        if sequences != sorted(sequences):
            raise ValueError("edge sequences must be in increasing order")


class InputEdgeQueue:
    """Collects input edges until one eligible simulation step consumes them.

    Every call to consume_for_step drains the queue. A command rejected by
    gameplay rules is still consumed and must not become a later drop.
    """

    __slots__ = ("_edges", "_last_sequence")

    def __init__(self) -> None:
        self._edges: deque[InputEdge] = deque()
        self._last_sequence = -1

    def enqueue(self, edge: InputEdge) -> None:
        if edge.sequence <= self._last_sequence:
            raise ValueError("input edge sequence must increase monotonically")
        self._edges.append(edge)
        self._last_sequence = edge.sequence

    def enqueue_frame(self, frame: InputFrame) -> None:
        for edge in frame.edges:
            self.enqueue(edge)

    def consume_for_step(self) -> tuple[InputEdge, ...]:
        """Return pending edges once, clearing them even if the caller rejects them."""

        edges = tuple(self._edges)
        self._edges.clear()
        return edges

    def clear(self) -> None:
        """Discard edges on pause, focus loss, disconnect, or scene change."""

        self._edges.clear()
