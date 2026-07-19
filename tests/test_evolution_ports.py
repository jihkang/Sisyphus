from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest

from sisyphus.application.commands.evolution import RequestEvolutionFollowupCommand
from sisyphus.evolution.dataset import project_evolution_dataset
from sisyphus.infra.evolution.run_store import RepositoryEvolutionRunStore
from sisyphus.shared.paths import PathBoundaryError


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T00:00:00Z"


class TaskQueryFake:
    repo_root = Path("/repo")

    def list(self):
        return (
            {
                "id": "TF-2",
                "slug": "two",
                "type": "feature",
                "status": "open",
                "updated_at": "2026-07-19T02:00:00Z",
            },
            {
                "id": "TF-1",
                "slug": "one",
                "type": "feature",
                "status": "open",
                "updated_at": "2026-07-19T01:00:00Z",
            },
        )

    def load_with_path(self, task_id):
        raise AssertionError("dataset projection must not request mutable task access")


class EventPortFake:
    locator = Path("/repo/.planning/events.jsonl")

    def read(self, *, limit):
        self.limit = limit
        return (
            {"event_id": "evt-1", "event_type": "task.updated", "data": {"task_id": "TF-1"}},
            {"event_id": "evt-2", "event_type": "task.updated", "data": {"task_id": "TF-2"}},
        )

    def publish(self, **kwargs):
        raise AssertionError("dataset projection is read-only")


class EvolutionPortTests(unittest.TestCase):
    def test_dataset_projection_uses_read_only_ports_and_stable_clock(self) -> None:
        events = EventPortFake()

        dataset = project_evolution_dataset(
            TaskQueryFake(),
            events,
            FixedClock(),
            task_ids=("TF-1",),
            max_events=7,
        )

        self.assertEqual(dataset.generated_at, "2026-07-19T00:00:00Z")
        self.assertEqual(dataset.selected_task_ids, ("TF-1",))
        self.assertEqual(tuple(trace.event_id for trace in dataset.event_traces), ("evt-1",))
        self.assertEqual(events.limit, 7)

    def test_followup_command_has_no_lifecycle_authority_fields(self) -> None:
        command = RequestEvolutionFollowupCommand(
            message="review this candidate",
            title="Candidate follow-up",
            task_type="feature",
            slug="candidate-followup",
            instruction=None,
        )

        forbidden = {"approve", "freeze", "verify", "promote", "activate", "close"}
        self.assertFalse(forbidden.intersection(command.__dataclass_fields__))

    def test_run_store_rejects_unsafe_run_ids_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, tempfile.TemporaryDirectory() as outside:
            repo_root = Path(tempdir)
            store = RepositoryEvolutionRunStore(repo_root)

            for run_id in ("", "../escape", "/tmp/escape", "nested/run", ".hidden"):
                with self.subTest(run_id=run_id):
                    with self.assertRaises(ValueError):
                        store.artifact_dir(run_id)

            runs_root = repo_root / ".planning" / "evolution" / "runs"
            runs_root.mkdir(parents=True)
            os.symlink(Path(outside), runs_root / "EVR-symlink")
            with self.assertRaises(PathBoundaryError):
                store.append_text("EVR-symlink", "report.md", "blocked")

    def test_run_store_is_append_only_and_does_not_follow_artifact_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, tempfile.TemporaryDirectory() as outside:
            repo_root = Path(tempdir)
            outside_file = Path(outside) / "outside.txt"
            outside_file.write_text("original", encoding="utf-8")
            store = RepositoryEvolutionRunStore(repo_root)
            run_dir = store.create_run("EVR-safe")

            store.append_json("EVR-safe", "run.json", {"run": {"run_id": "EVR-safe"}})
            with self.assertRaises(FileExistsError):
                store.append_json("EVR-safe", "run.json", {"run": {"run_id": "changed"}})

            os.symlink(outside_file, run_dir / "report.md")
            with self.assertRaises(PathBoundaryError):
                store.append_text("EVR-safe", "report.md", "overwrite")

            self.assertEqual(outside_file.read_text(encoding="utf-8"), "original")
            self.assertEqual(store.read_json("EVR-safe", "run.json")["run"]["run_id"], "EVR-safe")

    def test_run_store_enforces_bounded_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = RepositoryEvolutionRunStore(Path(tempdir), read_limit=8)
            store.create_run("EVR-bounded")
            store.append_text("EVR-bounded", "report.md", "123456789")

            with self.assertRaisesRegex(ValueError, "exceeds read limit"):
                store.read_text("EVR-bounded", "report.md")


if __name__ == "__main__":
    unittest.main()
