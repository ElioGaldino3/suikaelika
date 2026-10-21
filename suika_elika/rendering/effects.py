"""Bounded presentation-only particles with a private random generator."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import cos, isfinite, sin, tau

from suika_elika.contracts import DomainEvent, EventType, Vector2

MAX_PARTICLES = 128
MAX_SEEN_EVENTS = 512


@dataclass(slots=True)
class Particle:
    position: Vector2
    velocity: Vector2
    age: float
    lifetime: float
    color: tuple[int, int, int]
    radius: float


@dataclass(slots=True)
class Flash:
    position: Vector2
    age: float
    lifetime: float


class EffectSystem:
    """Create short, capped merge effects independent of fruit RNG/state."""

    def __init__(self, *, seed: int = 0, max_particles: int = MAX_PARTICLES) -> None:
        if type(max_particles) is not int or not 0 <= max_particles <= MAX_PARTICLES:
            raise ValueError(f"max_particles must be between 0 and {MAX_PARTICLES}")
        self._random = random.Random(seed)
        self.max_particles = max_particles
        self.particles: list[Particle] = []
        self.flashes: list[Flash] = []
        self._seen_events: set[tuple[EventType, int, tuple[str, ...]]] = set()
        self._seen_order: list[tuple[EventType, int, tuple[str, ...]]] = []

    def update(
        self,
        delta_seconds: float,
        events: tuple[DomainEvent, ...] = (),
        *,
        reduced: bool = False,
    ) -> None:
        """Advance effect clocks and consume each simulation event only once."""
        if not isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("effect delta must be finite and non-negative")
        if type(reduced) is not bool:
            raise TypeError("reduced must be a boolean")
        self.particles = [
            particle
            for particle in self.particles
            if self._advance_particle(particle, delta_seconds)
        ]
        self.flashes = [
            flash
            for flash in self.flashes
            if self._advance_flash(flash, delta_seconds)
        ]
        for event in events:
            key = (event.event_type, event.step_index, event.entity_ids)
            if key in self._seen_events:
                continue
            self._remember(key)
            if event.event_type is EventType.FRUIT_MERGED and event.position is not None:
                self._emit_merge(event.position, reduced=reduced)

    def clear(self) -> None:
        self.particles.clear()
        self.flashes.clear()
        self._seen_events.clear()
        self._seen_order.clear()

    def _emit_merge(self, position: Vector2, *, reduced: bool) -> None:
        amount = min(self.max_particles - len(self.particles), 3 if reduced else 9)
        for _ in range(max(0, amount)):
            angle = self._random.random() * tau
            speed = self._random.uniform(18.0, 72.0)
            self.particles.append(
                Particle(
                    position=position,
                    velocity=Vector2(cos(angle) * speed, sin(angle) * speed - 16.0),
                    age=0.0,
                    lifetime=self._random.uniform(0.2, 0.48),
                    color=self._random.choice(
                        ((249, 201, 71), (255, 247, 220), (90, 181, 156), (228, 85, 85))
                    ),
                    radius=self._random.uniform(2.0, 5.0),
                )
            )
        if not reduced:
            self.flashes.append(Flash(position=position, age=0.0, lifetime=0.16))

    @staticmethod
    def _advance_particle(particle: Particle, delta: float) -> bool:
        particle.age += delta
        if particle.age >= particle.lifetime:
            return False
        particle.position = Vector2(
            particle.position.x + particle.velocity.x * delta,
            particle.position.y + particle.velocity.y * delta,
        )
        particle.velocity = Vector2(particle.velocity.x, particle.velocity.y + 120.0 * delta)
        return True

    @staticmethod
    def _advance_flash(flash: Flash, delta: float) -> bool:
        flash.age += delta
        return flash.age < flash.lifetime

    def _remember(self, key: tuple[EventType, int, tuple[str, ...]]) -> None:
        self._seen_events.add(key)
        self._seen_order.append(key)
        if len(self._seen_order) > MAX_SEEN_EVENTS:
            expired = self._seen_order.pop(0)
            self._seen_events.discard(expired)


__all__ = ["EffectSystem", "Flash", "MAX_PARTICLES", "Particle"]
