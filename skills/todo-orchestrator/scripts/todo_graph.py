"""Read-only validation and conservative scheduling for a Markdown backlog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ID = r"[A-Z]+-[0-9]{3,}"
HEADING = re.compile(rf"^### ({ID}) [—–-] (.+)$", re.MULTILINE)
ANY_HEADING = re.compile(r"^### (.+)$", re.MULTILINE)
BOUNDARY = re.compile(r"^#{2,3} ", re.MULTILINE)
FIELD = re.compile(r"^- ([A-Za-z]+): (.+)$", re.MULTILINE)
REQUIRED = {
    "Status", "Scope", "Priority", "Depends", "Writes", "Reads",
    "Owner", "Attempts", "Evidence", "Blocker",
}
STATES = {"pending", "in_progress", "in_review", "done", "blocked", "deferred"}
ACTIVE = {"in_progress", "in_review"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)
}


class BacklogError(ValueError):
    """The backlog cannot safely be scheduled."""


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: str
    scope: str
    priority: str
    depends: tuple[str, ...]
    writes: tuple[str, ...]
    reads: tuple[str, ...]
    owner: str
    attempts: int
    evidence: str
    blocker: str


def scalar(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def paths(value: str, task_id: str) -> tuple[str, ...]:
    if value == "none":
        return ()
    result = tuple(part.strip() for part in value.split(";"))
    for path in result:
        base = path[:-3] if path.endswith("/**") else path
        parts = base.split("/")
        if (
            not base or "\\" in path or ":" in path or path.startswith(("/", "~"))
            or any(p in {"", ".", ".."} for p in parts)
            or parts[0].casefold() == ".git"
            or any(c in base for c in '*?[]`<>"|')
            or any(ord(c) < 32 for c in base)
            or any(p.endswith((".", " ")) for p in parts)
            or any(p.split(".")[0].casefold() in WINDOWS_RESERVED for p in parts)
        ):
            raise BacklogError(f"{task_id}: unsafe/unsupported path: {path!r}")
    if len({p.casefold() for p in result}) != len(result):
        raise BacklogError(f"{task_id}: duplicate paths")
    return result


def overlaps(left: str, right: str) -> bool:
    a_tree, b_tree = left.endswith("/**"), right.endswith("/**")
    a = (left[:-3] if a_tree else left).casefold()
    b = (right[:-3] if b_tree else right).casefold()
    return a == b or (a_tree and b.startswith(a + "/")) or (
        b_tree and a.startswith(b + "/")
    )


def conflicts(left: Task, right: Task) -> list[str]:
    found = {
        f"{a} <-> {b}"
        for a in left.writes for b in (*right.writes, *right.reads)
        if overlaps(a, b)
    }
    found.update(
        f"{a} <-> {b}" for a in left.reads for b in right.writes if overlaps(a, b)
    )
    return sorted(found)


def visible_markdown(text: str) -> str:
    """Ignore fenced examples so they can never become executable backlog cards."""
    visible: list[str] = []
    fence_char = ""
    fence_size = 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        was_inside = bool(fence_char)
        if fence:
            marker, suffix = fence.groups()
            if not fence_char:
                fence_char, fence_size = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_size and not suffix.strip():
                fence_char, fence_size = "", 0
        visible.append("\n" if was_inside or fence_char or fence else line)
    if fence_char:
        raise BacklogError("Unclosed fenced block; task visibility is ambiguous")
    return "".join(visible)


def parse(text: str) -> list[Task]:
    text = visible_markdown(text)
    tasks: list[Task] = []
    seen: set[str] = set()
    for heading in ANY_HEADING.finditer(text):
        following = BOUNDARY.search(text, heading.end())
        block = text[heading.end():following.start() if following else len(text)]
        if not HEADING.fullmatch(heading.group()) and any(
            field in REQUIRED for field, _ in FIELD.findall(block)
        ):
            raise BacklogError(f"Malformed task heading: {heading.group()}")
    for match in HEADING.finditer(text):
        task_id, title = match.groups()
        if task_id in seen:
            raise BacklogError(f"Duplicate task ID: {task_id}")
        seen.add(task_id)
        following = BOUNDARY.search(text, match.end())
        end = following.start() if following else len(text)
        block = text[match.end():end]
        fields: dict[str, str] = {}
        for field, value in FIELD.findall(block):
            if field not in REQUIRED:
                continue
            if field in fields:
                raise BacklogError(f"{task_id}: duplicate field {field}")
            fields[field] = scalar(value)
        missing = REQUIRED - fields.keys()
        if missing:
            raise BacklogError(f"{task_id}: missing fields: {', '.join(sorted(missing))}")
        if fields["Status"] not in STATES:
            raise BacklogError(f"{task_id}: invalid status")
        if fields["Priority"] not in {"P0", "P1", "P2", "P3"}:
            raise BacklogError(f"{task_id}: invalid priority")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", fields["Scope"]):
            raise BacklogError(f"{task_id}: invalid scope")
        if not fields["Attempts"].isascii() or not fields["Attempts"].isdigit():
            raise BacklogError(f"{task_id}: Attempts must be a nonnegative integer")
        depends = () if fields["Depends"] == "none" else tuple(
            p.strip() for p in fields["Depends"].split(",")
        )
        if any(not re.fullmatch(ID, dep) for dep in depends):
            raise BacklogError(f"{task_id}: invalid dependency ID")
        if len(set(depends)) != len(depends):
            raise BacklogError(f"{task_id}: duplicate dependencies")
        acceptance = re.search(r"^\*\*(?:Aceitação|Acceptance):\*\*", block, re.MULTILINE)
        if not acceptance:
            raise BacklogError(f"{task_id}: missing acceptance criteria section")
        criteria = []
        for line in block[acceptance.end():].splitlines():
            if line.startswith("- "):
                item = re.sub(r"^\[[ xX]\]\s*", "", line[2:].strip()).strip()
                if item:
                    criteria.append(item)
        if not criteria:
            raise BacklogError(f"{task_id}: acceptance criteria cannot be empty")
        tasks.append(Task(
            task_id, title, fields["Status"], fields["Scope"], fields["Priority"],
            depends, paths(fields["Writes"], task_id), paths(fields["Reads"], task_id),
            fields["Owner"], int(fields["Attempts"]), fields["Evidence"], fields["Blocker"],
        ))
    if not tasks:
        raise BacklogError("No task cards found")
    validate(tasks)
    return tasks


def validate(tasks: Sequence[Task]) -> None:
    by_id = {task.id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise BacklogError("Duplicate task IDs")
    for task in tasks:
        for dep in task.depends:
            if dep not in by_id:
                raise BacklogError(f"{task.id}: unknown dependency {dep}")
        if task.status in ACTIVE:
            if task.owner in {"unassigned", "none", ""} or task.attempts < 1:
                raise BacklogError(f"{task.id}: active task needs owner and Attempts >= 1")
        elif task.owner != "unassigned":
            raise BacklogError(f"{task.id}: inactive task must release its owner")
        if task.status == "blocked":
            if task.blocker.casefold() in {"none", "", "pending"}:
                raise BacklogError(f"{task.id}: blocked task needs a concrete blocker")
        elif task.blocker != "none":
            raise BacklogError(f"{task.id}: nonblocked task has a blocker")
        if task.status == "done":
            evidence = task.evidence.casefold()
            if len(evidence) < 12 or evidence.startswith(("none", "pending", "ainda não", "a registrar")):
                raise BacklogError(f"{task.id}: done task needs verification evidence")
            if task.attempts < 1:
                raise BacklogError(f"{task.id}: done task needs Attempts >= 1")
        if task.status in ACTIVE | {"done"}:
            incomplete = [dep for dep in task.depends if by_id[dep].status != "done"]
            if incomplete:
                raise BacklogError(f"{task.id}: active/done with incomplete dependencies: {incomplete}")

    visited: set[str] = set()
    visiting: list[str] = []

    def visit(task_id: str) -> None:
        if task_id in visiting:
            cycle = visiting[visiting.index(task_id):] + [task_id]
            raise BacklogError("Dependency cycle: " + " -> ".join(cycle))
        if task_id in visited:
            return
        visiting.append(task_id)
        for dep in by_id[task_id].depends:
            visit(dep)
        visiting.pop()
        visited.add(task_id)

    for task in tasks:
        visit(task.id)
    active = [task for task in tasks if task.status in ACTIVE]
    owners: set[str] = set()
    for index, task in enumerate(active):
        if task.owner in owners:
            raise BacklogError(f"Owner has more than one active task: {task.owner}")
        owners.add(task.owner)
        for other in active[index + 1:]:
            collision = conflicts(task, other)
            if collision:
                raise BacklogError(f"Active reservation conflict {task.id}/{other.id}: {collision}")


def ready_tasks(tasks: Sequence[Task], scope: str) -> list[Task]:
    by_id = {task.id: task for task in tasks}
    return sorted(
        (task for task in tasks if task.scope == scope and task.status == "pending"
         and all(by_id[dep].status == "done" for dep in task.depends)),
        key=lambda task: (task.priority, task.id),
    )


def plan(tasks: Sequence[Task], scope: str, team_slots: int, max_workers: int) -> dict[str, object]:
    if team_slots < 1 or not 0 <= max_workers <= 4:
        raise BacklogError("team-slots must be >= 1 and max-workers must be between 0 and 4")
    validate(tasks)
    active = [task for task in tasks if task.status in ACTIVE]
    child_owners = {task.owner for task in active if task.owner != "root"}
    capacity = min(4, max_workers, team_slots - 1)
    remaining = max(0, capacity - len(child_owners))
    selected: list[Task] = []
    skipped: list[dict[str, object]] = []
    for candidate in ready_tasks(tasks, scope):
        blockers = [task.id for task in (*active, *selected) if conflicts(candidate, task)]
        if blockers:
            skipped.append({"id": candidate.id, "reason": "reservation_conflict", "with": blockers})
        elif len(selected) >= remaining:
            skipped.append({"id": candidate.id, "reason": "capacity"})
        else:
            selected.append(candidate)
    return {
        "scope": scope, "team_slots_including_root": team_slots,
        "max_simultaneous_subagents": capacity, "active_child_owners": sorted(child_owners),
        "additional_assignments": [asdict(task) for task in selected], "not_selected": skipped,
        "notice": "Read-only suggestion; account for live agents/reviewers outside TODO before dispatch.",
    }


def report(tasks: Sequence[Task], scope: str) -> dict[str, object]:
    relevant = [task for task in tasks if task.scope == scope]
    by_id = {task.id: task for task in tasks}
    return {
        "scope": scope, "counts": dict(Counter(task.status for task in relevant)),
        "ready": [task.id for task in ready_tasks(tasks, scope)],
        "explicit_blockers": {task.id: task.blocker for task in relevant if task.status == "blocked"},
        "waiting_dependencies": {
            task.id: [dep for dep in task.depends if by_id[dep].status != "done"]
            for task in relevant if task.status == "pending"
            and any(by_id[dep].status != "done" for dep in task.depends)
        },
        "complete": bool(relevant) and all(task.status == "done" for task in relevant),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "plan", "report"))
    parser.add_argument("--todo", type=Path, default=Path("TODO.md"))
    parser.add_argument("--scope", default="mvp")
    parser.add_argument("--team-slots", type=int, default=1)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        tasks = parse(args.todo.read_text(encoding="utf-8-sig"))
        if args.command == "validate":
            result: dict[str, object] = {"valid": True, "tasks": len(tasks)}
        elif args.command == "plan":
            result = plan(tasks, args.scope, args.team_slots, args.max_workers)
        else:
            result = report(tasks, args.scope)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
