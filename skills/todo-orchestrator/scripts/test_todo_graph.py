"""Behavioral checks with synthetic backlogs; never execute the game backlog."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import todo_graph as graph


def card(
    task_id: str = "EX-001", *, depends: str = "none", writes: str = "pkg/a.py",
    reads: str = "docs/spec.md", status: str = "pending", owner: str = "unassigned",
    attempts: int = 0, blocker: str = "none", evidence: str = "Ainda não executada.",
    scope: str = "mvp", priority: str = "P1",
) -> str:
    return f"""### {task_id} — Example

- Status: `{status}`
- Scope: `{scope}`
- Priority: `{priority}`
- Depends: `{depends}`
- Writes: `{writes}`
- Reads: `{reads}`
- Owner: `{owner}`
- Attempts: `{attempts}`
- Evidence: {evidence}
- Blocker: `{blocker}`

**Aceitação:**
- Observable result and a relevant check.

"""


class GraphTests(unittest.TestCase):
    def test_independent_tasks_and_dependencies(self) -> None:
        tasks = graph.parse(card() + card("EX-002", writes="pkg/b.py")
                            + card("EX-003", depends="EX-001, EX-002", writes="pkg/c.py"))
        self.assertEqual([t.id for t in graph.ready_tasks(tasks, "mvp")], ["EX-001", "EX-002"])

    def test_completed_dependency_releases_consumer(self) -> None:
        tasks = graph.parse(card(status="done", attempts=1, evidence="Unit checks passed; diff reviewed.")
                            + card("EX-002", depends="EX-001", writes="pkg/b.py"))
        self.assertEqual([t.id for t in graph.ready_tasks(tasks, "mvp")], ["EX-002"])

    def test_four_total_slots_mean_three_subagents(self) -> None:
        tasks = graph.parse("".join(card(f"EX-{i:03d}", writes=f"pkg/{i}.py") for i in range(1, 7)))
        result = graph.plan(tasks, "mvp", 4, 4)
        self.assertEqual(len(result["additional_assignments"]), 3)  # type: ignore[arg-type]

    def test_four_subagents_hard_cap_and_no_capacity_default(self) -> None:
        tasks = graph.parse("".join(card(f"EX-{i:03d}", writes=f"pkg/{i}.py") for i in range(1, 7)))
        self.assertEqual(len(graph.plan(tasks, "mvp", 99, 4)["additional_assignments"]), 4)  # type: ignore[arg-type]
        self.assertEqual(graph.plan(tasks, "mvp", 1, 4)["additional_assignments"], [])

    def test_active_worker_uses_capacity(self) -> None:
        tasks = graph.parse(card(status="in_review", owner="agent-1", attempts=1)
                            + "".join(card(f"EX-{i:03d}", writes=f"pkg/{i}.py") for i in range(2, 6)))
        self.assertEqual(len(graph.plan(tasks, "mvp", 4, 4)["additional_assignments"]), 2)  # type: ignore[arg-type]

    def test_root_reservation_does_not_use_extra_child_slot(self) -> None:
        tasks = graph.parse(card(status="in_progress", owner="root", attempts=1)
                            + card("EX-002", writes="pkg/b.py"))
        self.assertEqual(len(graph.plan(tasks, "mvp", 2, 4)["additional_assignments"]), 1)  # type: ignore[arg-type]

    def test_same_file_serialized(self) -> None:
        tasks = graph.parse(card() + card("EX-002"))
        result = graph.plan(tasks, "mvp", 4, 4)
        self.assertEqual(len(result["additional_assignments"]), 1)  # type: ignore[arg-type]

    def test_subtrees_and_case_collisions(self) -> None:
        self.assertTrue(graph.overlaps("Pkg/**", "pkg/a.py"))
        self.assertTrue(graph.overlaps("pkg/inner/**", "PKG/**"))
        self.assertFalse(graph.overlaps("pkg/a.py", "pkg/b.py"))
        self.assertFalse(graph.overlaps("pkg/**", "pkg2/a.py"))

    def test_reader_writer_conflict(self) -> None:
        tasks = graph.parse(card(writes="pkg/model.py")
                            + card("EX-002", writes="pkg/view.py", reads="pkg/model.py"))
        self.assertEqual(len(graph.plan(tasks, "mvp", 4, 4)["additional_assignments"]), 1)  # type: ignore[arg-type]

    def test_existing_reservation_blocks_dispatch(self) -> None:
        tasks = graph.parse(card(status="in_progress", owner="agent-1", attempts=1, writes="pkg/**")
                            + card("EX-002", writes="pkg/b.py"))
        self.assertEqual(graph.plan(tasks, "mvp", 4, 4)["additional_assignments"], [])

    def test_invalid_active_overlap_rejected(self) -> None:
        with self.assertRaises(graph.BacklogError):
            graph.parse(card(status="in_progress", owner="a", attempts=1)
                        + card("EX-002", status="in_review", owner="b", attempts=1))

    def test_cycle_unknown_dependency_and_duplicate_ids(self) -> None:
        examples = [card(depends="EX-002") + card("EX-002", depends="EX-001"),
                    card(depends="EX-999"), card() + card()]
        for example in examples:
            with self.subTest(example=example), self.assertRaises(graph.BacklogError):
                graph.parse(example)

    def test_blocked_hardware_does_not_block_independent_work(self) -> None:
        tasks = graph.parse(card(status="blocked", blocker="Hardware unavailable; supply the target.")
                            + card("EX-002", writes="pkg/b.py"))
        self.assertEqual([t.id for t in graph.ready_tasks(tasks, "mvp")], ["EX-002"])
        self.assertFalse(graph.report(tasks, "mvp")["complete"])

    def test_false_done_and_active_before_dependencies_rejected(self) -> None:
        invalid = [card(status="done", attempts=1),
                   card(status="in_progress", owner="unassigned", attempts=1),
                   card() + card("EX-002", depends="EX-001", status="in_progress", owner="a", attempts=1)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(graph.BacklogError):
                graph.parse(text)

    def test_unsafe_paths_rejected(self) -> None:
        for path in ("../secret", "C:/secret", "/etc/passwd", ".git/index", "pkg/../x", "pkg/*.py", "pkg\\x", "pkg//x", "pkg/a.py.", "pkg./a.py", "pkg/NUL.txt", "pkg/a|b.py"):
            with self.subTest(path=path), self.assertRaises(graph.BacklogError):
                graph.parse(card(writes=path))

    def test_future_scope_and_deferred_not_implicitly_started(self) -> None:
        tasks = graph.parse(card(scope="future", status="deferred")
                            + card("EX-002", writes="pkg/b.py"))
        self.assertEqual([t.id for t in graph.ready_tasks(tasks, "mvp")], ["EX-002"])
        self.assertEqual(graph.ready_tasks(tasks, "future"), [])

    def test_priority_and_missing_fields(self) -> None:
        tasks = graph.parse(card(priority="P2") + card("EX-002", priority="P0", writes="pkg/b.py"))
        self.assertEqual(graph.ready_tasks(tasks, "mvp")[0].id, "EX-002")
        with self.assertRaises(graph.BacklogError):
            graph.parse(card().replace("- Owner: `unassigned`\n", ""))

    def test_duplicate_owner_and_invalid_metadata(self) -> None:
        with self.assertRaises(graph.BacklogError):
            graph.parse(card(status="in_progress", owner="a", attempts=1)
                        + card("EX-002", status="in_progress", owner="a", attempts=1, writes="pkg/b.py"))
        for text in (card(status="unknown"), card(priority="P9"), card(attempts=-1), card(status="blocked")):
            with self.subTest(text=text), self.assertRaises(graph.BacklogError):
                graph.parse(text)

    def test_no_tasks_does_not_mean_complete(self) -> None:
        with self.assertRaises(graph.BacklogError):
            graph.parse("# Notes only")
        self.assertFalse(graph.report([], "mvp")["complete"])

    def test_malformed_task_is_not_silently_hidden(self) -> None:
        complete = card(status="done", attempts=1, evidence="Checks passed and criteria verified.")
        with self.assertRaises(graph.BacklogError):
            graph.parse(complete + card("EX-02"))
        tasks = graph.parse(card().replace(" — ", " – "))
        self.assertEqual(tasks[0].id, "EX-001")

    def test_fenced_examples_never_dispatch(self) -> None:
        for fence in ("```", "~~~~"):
            text = card() + fence + "markdown\n" + card("EX-002") + fence + "\n"
            self.assertEqual([t.id for t in graph.parse(text)], ["EX-001"])
        with self.assertRaises(graph.BacklogError):
            graph.parse(card() + "```markdown\n" + card("EX-002"))

    def test_empty_acceptance_is_rejected(self) -> None:
        for criteria in ("", "- [ ] \n", "- \n"):
            text = card().replace("- Observable result and a relevant check.\n", criteria)
            with self.assertRaises(graph.BacklogError):
                graph.parse(text)

    def test_cli_read_only_and_invalid_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "TODO.md"
            path.write_text(card(), encoding="utf-8")
            original = path.read_bytes()
            for command in ("validate", "plan", "report"):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(graph.main([command, "--todo", str(path)]), 0)
                self.assertEqual(path.read_bytes(), original)
            path.write_text(card(depends="EX-999"), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(graph.main(["validate", "--todo", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
