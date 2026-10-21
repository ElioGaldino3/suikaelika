"""Fixed-step orchestration for one ruleset-bound game round."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite

from suika_elika.contracts import (
    DomainEvent,
    EventType,
    FruitDefinition,
    FruitSnapshot,
    InputAction,
    InputEdgeQueue,
    InputFrame,
    PersistencePort,
    PhysicsPort,
    Pose,
    RecordData,
    RoundState,
    SessionSnapshot,
    StatisticsData,
    Vector2,
    make_event,
)
from suika_elika.game.catalog import FruitCatalog, load_catalog
from suika_elika.game.danger import (
    DangerConfig,
    DangerObservation,
    DangerSystem,
    GameOverReason,
)
from suika_elika.game.merging import MergeFruit, MergeResolution, MergeSystem
from suika_elika.game.randomizer import FruitSequence
from suika_elika.game.spawning import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    FruitLauncher,
    LauncherState,
)

DEFAULT_FIXED_DT = 1.0 / 120.0
DEFAULT_DIGITAL_SPEED = 420.0
DEFAULT_FINE_SPEED = 100.0


@dataclass(frozen=True, slots=True)
class _FruitState:
    definition: FruitDefinition
    previous_pose: Pose
    pose: Pose
    velocity: Vector2


class _EntityIds:
    """Small monotonic ID source shared by launches and merge children."""

    def __init__(self) -> None:
        self._next = 1

    def __call__(self) -> str:
        value = f"fruit-{self._next:06d}"
        self._next += 1
        return value


class GameSession:
    """Own game rules and coordinate systems in a fixed, render-free order.

    One call to :meth:`step` is one fixed physics step. The application owns the
    real-time accumulator. ``launch_contacted`` is an explicit integration seam
    for wall/floor contacts: the current PhysicsPort reports fruit-to-fruit
    contacts only, so this class never guesses static geometry collisions from
    a body's position. Fruit-pair contacts and consumption by a merge are
    detected internally. The launcher release interval is independent of contact.
    """

    def __init__(
        self,
        physics: PhysicsPort,
        *,
        catalog: FruitCatalog | None = None,
        seed: int | str | bytes | bytearray = 0,
        persistence: PersistencePort | None = None,
        entity_id_factory: Callable[[], str] | None = None,
        mode: str = "classic",
        width: float = DEFAULT_WIDTH,
        height: float = DEFAULT_HEIGHT,
        fixed_dt: float = DEFAULT_FIXED_DT,
        digital_speed: float = DEFAULT_DIGITAL_SPEED,
        fine_speed: float = DEFAULT_FINE_SPEED,
    ) -> None:
        if not mode:
            raise ValueError("mode must not be empty")
        if any(
            not isfinite(value) or value <= 0
            for value in (width, height, fixed_dt, digital_speed, fine_speed)
        ):
            raise ValueError("world dimensions, fixed step, and movement speeds must be positive")
        if fine_speed > digital_speed:
            raise ValueError("fine movement speed must not exceed digital speed")
        self._physics = physics
        self._catalog = catalog or load_catalog()
        self._persistence = persistence
        self._id_factory = entity_id_factory or _EntityIds()
        self._mode = mode
        self._width = width
        self._height = height
        self._fixed_dt = fixed_dt
        self._digital_speed = digital_speed
        self._fine_speed = fine_speed
        self._seed = seed
        self._records = self._load_records()
        self._statistics = self._load_statistics()
        self._high_score = self._read_high_score()
        self._edges = InputEdgeQueue()
        self._fruits: dict[str, _FruitState] = {}
        self._round_state = RoundState.READY
        self._score = 0
        self._merge_count = 0
        self._drop_count = 0
        self._best_fruit_level = 0
        self._watermelons = 0
        self._duration_seconds = 0.0
        self._danger_progress = 0.0
        self._warning_entity_id: str | None = None
        self._step_index = 0
        self._events: tuple[DomainEvent, ...] = ()
        self._reset_round(seed)

    @property
    def ruleset_version(self) -> str:
        return self._catalog.ruleset_version

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def round_state(self) -> RoundState:
        return self._round_state

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        """Copied events produced by the most recent fixed step."""
        return self._events

    @property
    def score(self) -> int:
        return self._score

    @property
    def high_score(self) -> int:
        return self._high_score

    @property
    def merge_count(self) -> int:
        return self._merge_count

    @property
    def drop_count(self) -> int:
        return self._drop_count

    @property
    def best_fruit_level(self) -> int:
        return self._best_fruit_level

    @property
    def watermelons(self) -> int:
        return self._watermelons

    @property
    def double_watermelon_pairs(self) -> int:
        """Number of completed pairs of top-level fruits in this round."""
        return self._double_watermelon_pairs

    @property
    def duration_seconds(self) -> float:
        return self._duration_seconds

    @property
    def statistics(self) -> StatisticsData:
        """Global totals projected to include the current unfinished round."""
        if self._round_state is RoundState.GAME_OVER or self._drop_count == 0:
            return self._statistics
        return StatisticsData(
            sessions_played=self._statistics.sessions_played + 1,
            merges=self._statistics.merges + self._merge_count,
            best_fruit_level=max(
                self._statistics.best_fruit_level, self._best_fruit_level
            ),
            watermelons=self._statistics.watermelons + self._watermelons,
        )

    @property
    def snapshot(self) -> SessionSnapshot:
        danger_by_id = {state.entity_id: state for state in self._danger.states}
        fruit_snapshots = tuple(
            FruitSnapshot(
                entity_id=entity_id,
                fruit_id=state.definition.fruit_id,
                previous_pose=state.previous_pose,
                current_pose=state.pose,
                danger_eligible=danger_by_id[entity_id].danger_eligible,
                danger_seconds=danger_by_id[entity_id].danger_seconds,
            )
            for entity_id, state in sorted(self._fruits.items())
        )
        launcher = self._launcher.snapshot
        terminal = self._round_state is RoundState.GAME_OVER
        return SessionSnapshot(
            score=self._score,
            high_score=self._high_score,
            current_fruit=None if terminal else launcher.current,
            next_fruit=None if terminal else launcher.next,
            fruits=fruit_snapshots,
            launcher_x=launcher.launcher_x,
            drop_ready=(
                not terminal
                and self._round_state is not RoundState.PAUSED
                and launcher.state is LauncherState.READY
            ),
            danger_progress=self._danger_progress,
            round_state=self._round_state,
        )

    def step(
        self,
        frame: InputFrame | None = None,
        *,
        launch_contacted: bool = False,
    ) -> tuple[DomainEvent, ...]:
        """Consume one frame and execute one fixed gameplay step unless paused.

        The caller can supply ``launch_contacted`` when its static-geometry
        contact source detects the active launch body touching a wall or floor.
        ``PhysicsPort.contacts()`` currently supplies only fruit pairs.
        """
        if type(launch_contacted) is not bool:
            raise TypeError("launch_contacted must be a bool")
        if frame is None:
            frame = InputFrame()
        self._events = ()
        if self._round_state in (RoundState.PAUSED, RoundState.GAME_OVER):
            self._edges.clear()
            return self._events

        self._edges.enqueue_frame(frame)
        self._move_launcher(frame.move_x, frame.fine_adjust)
        step_events: list[DomainEvent] = []
        for edge in self._edges.consume_for_step():
            if edge.action is not InputAction.DROP:
                continue
            dropped_definition = self._launcher.snapshot.current
            dropped_x = self._launcher.launcher_x
            result = self._launcher.handle_drop(edge)
            if result.accepted:
                assert result.entity_id is not None
                definition = dropped_definition
                pose = Pose(Vector2(dropped_x, self._launcher_y))
                self._fruits[result.entity_id] = _FruitState(definition, pose, pose, Vector2(0, 0))
                self._danger.register_spawn(result.entity_id)
                self._drop_count += 1
                self._best_fruit_level = max(self._best_fruit_level, definition.level)
                self._round_state = RoundState.PLAYING
                step_events.append(
                    make_event(
                        EventType.FRUIT_DROPPED,
                        self._step_index,
                        entity_ids=(result.entity_id,),
                        position=pose.position,
                        payload=(("fruit_id", definition.fruit_id),),
                    )
                )

        old_danger_progress = self._danger_progress
        if self._round_state is RoundState.PLAYING:
            self._duration_seconds += self._fixed_dt
        self._advance_physics_and_rules(launch_contacted=launch_contacted, events=step_events)
        if self._danger_progress != old_danger_progress:
            step_events.append(
                make_event(
                    EventType.DANGER_CHANGED,
                    self._step_index,
                    payload=(("progress", self._danger_progress),),
                )
            )
        self._events = tuple(step_events)
        self._step_index += 1
        return self._events

    def pause(self) -> None:
        """Freeze gameplay immediately and discard pending action edges."""
        if self._round_state in (RoundState.READY, RoundState.PLAYING):
            self._round_state = RoundState.PAUSED
            self._edges.clear()
            self._events = ()

    def resume(self) -> None:
        """Resume the same round without consuming the confirmation press."""
        if self._round_state is RoundState.PAUSED:
            self._round_state = RoundState.PLAYING if self._drop_count else RoundState.READY
            self._edges.clear()
            self._events = ()

    def restart(self, seed: int | str | bytes | bytearray | None = None) -> None:
        """Start an empty round and clear all bodies and residual commands."""
        for entity_id in tuple(self._fruits):
            self._physics.remove_body(entity_id)
        self._edges.clear()
        self._reset_round(self._seed if seed is None else seed)

    def _reset_round(self, seed: int | str | bytes | bytearray) -> None:
        self._seed = seed
        self._sequence = FruitSequence(seed, self._catalog)
        self._danger = DangerSystem(DangerConfig(width=self._width, height=self._height))
        self._launcher_y = -18.0
        self._launcher = FruitLauncher(
            self._sequence,
            self._physics,
            self._id_factory,
            width=self._width,
            height=self._height,
            launch_y=self._launcher_y,
        )
        self._merger = MergeSystem(
            self._catalog,
            self._physics,
            self._id_factory,
            width=self._width,
            height=self._height,
        )
        self._fruits = {}
        self._round_state = RoundState.READY
        self._score = 0
        self._merge_count = 0
        self._double_watermelon_pairs = 0
        self._drop_count = 0
        self._best_fruit_level = 0
        self._watermelons = 0
        self._duration_seconds = 0.0
        self._danger_progress = 0.0
        self._warning_entity_id = None
        self._step_index = 0
        self._events = ()

    def _move_launcher(self, move_x: float, fine_adjust: bool) -> None:
        speed = self._fine_speed if fine_adjust else self._digital_speed
        self._launcher.set_launcher_x(
            self._launcher.launcher_x + move_x * speed * self._fixed_dt
        )

    def _advance_physics_and_rules(
        self, *, launch_contacted: bool, events: list[DomainEvent]
    ) -> None:
        previous_poses = {entity_id: state.pose for entity_id, state in self._fruits.items()}
        self._physics.step()
        contacts = self._physics.contacts()
        contact_pairs = {
            entity_id
            for contact in contacts
            for entity_id in (contact.first_entity_id, contact.second_entity_id)
        }
        body_snapshots = self._physics.poses(tuple(sorted(self._fruits)))
        body_by_id = {body.entity_id: body for body in body_snapshots}

        merge_input: list[MergeFruit] = []
        for entity_id, state in sorted(self._fruits.items()):
            body = body_by_id.get(entity_id)
            if body is None:
                continue
            danger = self._danger.state(entity_id)
            merge_input.append(
                MergeFruit(
                    entity_id=entity_id,
                    definition=state.definition,
                    pose=body.pose,
                    velocity=body.velocity,
                    danger_eligible=danger.danger_eligible if danger else False,
                    danger_seconds=danger.danger_seconds if danger else 0.0,
                    protection_age_seconds=(
                        danger.protection_age_seconds if danger else None
                    ),
                )
            )
        resolution = self._merger.resolve(
            tuple(merge_input), step_index=self._step_index, contacts=contacts
        )
        merged_contact_ids: set[str] = set()
        self._apply_merge_resolution(
            resolution,
            previous_poses,
            events,
            merged_contact_ids=merged_contact_ids,
        )

        launch_id = self._launcher.snapshot.launch_entity_id
        self._launcher.advance(self._fixed_dt)

        observations = tuple(
            DangerObservation(
                entity_id=entity_id,
                center=state.pose.position,
                radius=state.definition.radius,
                contacted=(
                    entity_id in contact_pairs
                    or entity_id in merged_contact_ids
                    or (launch_contacted and entity_id == launch_id)
                ),
            )
            for entity_id, state in sorted(self._fruits.items())
        )
        danger_result = self._danger.update(observations, self._fixed_dt)
        self._danger_progress = danger_result.danger_progress
        self._warning_entity_id = danger_result.warning_entity_id
        if danger_result.reason is not None:
            self._finish(danger_result.reason, danger_result.game_over_entity_id, events)

    def _apply_merge_resolution(
        self,
        resolution: MergeResolution,
        previous_poses: dict[str, Pose],
        events: list[DomainEvent],
        *,
        merged_contact_ids: set[str],
    ) -> None:
        merged_parent_ids = {entity_id for pair in resolution.merged_pairs for entity_id in pair}
        for event in resolution.events:
            if event.event_type is not EventType.FRUIT_MERGED:
                continue
            if len(event.entity_ids) == 3:
                first_id, second_id, child_id = event.entity_ids
                self._danger.register_merge(child_id, (first_id, second_id))
                merged_contact_ids.add(child_id)
                self._merge_count += 1
                child_definition = self._definition_from_id(str(self._payload(event, "fruit_id")))
                if child_definition.level == 11:
                    self._watermelons += 1
            elif len(event.entity_ids) == 2:
                self._merge_count += 1
                self._double_watermelon_pairs += 1
            events.append(event)

        for event in resolution.events:
            if event.event_type is EventType.SCORE_CHANGED:
                raw_delta = self._payload(event, "delta")
                if type(raw_delta) is not int:
                    raise TypeError("score change delta must be an integer")
                delta = raw_delta
                self._score += delta
                events.append(event)
        for entity_id in merged_parent_ids:
            self._danger.remove(entity_id)
        self._fruits = {
            fruit.entity_id: _FruitState(
                definition=fruit.definition,
                previous_pose=previous_poses.get(fruit.entity_id, fruit.pose),
                pose=fruit.pose,
                velocity=fruit.velocity,
            )
            for fruit in resolution.fruits
        }
        self._best_fruit_level = max(
            [self._best_fruit_level]
            + [state.definition.level for state in self._fruits.values()]
        )
        if self._score > self._high_score:
            self._high_score = self._score
            self._save_record()

    def _finish(
        self,
        reason: GameOverReason,
        entity_id: str | None,
        events: list[DomainEvent],
    ) -> None:
        self._round_state = RoundState.GAME_OVER
        events.append(
            make_event(
                EventType.ROUND_ENDED,
                self._step_index,
                entity_ids=(entity_id,) if entity_id else (),
                payload=(("reason", reason.value),),
            )
        )
        if self._drop_count:
            self._statistics = StatisticsData(
                sessions_played=self._statistics.sessions_played + 1,
                merges=self._statistics.merges + self._merge_count,
                best_fruit_level=max(
                    self._statistics.best_fruit_level, self._best_fruit_level
                ),
                watermelons=self._statistics.watermelons + self._watermelons,
            )
            if self._persistence is not None:
                self._persistence.save_statistics(self._statistics)
            self._save_record()

    def _save_record(self) -> None:
        if self._persistence is None:
            return
        key = (self._mode, self.ruleset_version)
        previous = self._records.get(key)
        record = RecordData(
            ruleset_version=self.ruleset_version,
            mode=self._mode,
            score=max(previous.score if previous else 0, self._score),
            best_fruit_level=max(
                previous.best_fruit_level if previous else 0,
                self._best_fruit_level,
            ),
            watermelons=max(previous.watermelons if previous else 0, self._watermelons),
            duration_seconds=(
                self._duration_seconds
                if previous is None or self._score > previous.score
                else previous.duration_seconds
            ),
        )
        self._persistence.save_record(record)
        self._records[key] = record
        self._high_score = record.score

    def _load_records(self) -> dict[tuple[str, str], RecordData]:
        if self._persistence is None:
            return {}
        return {
            (record.mode, record.ruleset_version): record
            for record in self._persistence.load_records()
        }

    def _load_statistics(self) -> StatisticsData:
        if self._persistence is None:
            return StatisticsData()
        return self._persistence.load_statistics()

    def _read_high_score(self) -> int:
        record = self._records.get((self._mode, self._catalog.ruleset_version))
        return record.score if record is not None else 0

    def _definition_from_id(self, fruit_id: str) -> FruitDefinition:
        return self._catalog.get(fruit_id).definition

    @staticmethod
    def _payload(event: DomainEvent, key: str) -> str | int | float | bool | None:
        return dict(event.payload)[key]


__all__ = ["GameSession"]
