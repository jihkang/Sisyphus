from __future__ import annotations

import json
from pathlib import Path
import os
import shlex
import sys
import tempfile
import time
import unittest

from sisyphus.application.commands.evolution import RequestEvolutionFollowupCommand
from sisyphus.evolution.dataset import project_evolution_dataset
from sisyphus.evolution.harness import EvolutionWorktreeCommand
from sisyphus.infra.evolution.evaluation import RepositoryEvolutionCommandRunner
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

    def test_run_store_rejects_ancestor_symlink_substitution_after_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir, tempfile.TemporaryDirectory() as outside:
            repo_root = Path(tempdir)
            evolution_root = repo_root / ".planning" / "evolution"
            evolution_root.mkdir(parents=True)
            store = RepositoryEvolutionRunStore(repo_root)
            store.create_run("EVR-existing")
            outside_run = Path(outside) / "runs" / "EVR-existing"
            outside_run.mkdir(parents=True)
            outside_report = outside_run / "report.md"
            outside_report.write_text("outside baseline", encoding="utf-8")
            displaced = repo_root / ".planning" / "evolution-original"
            evolution_root.rename(displaced)
            evolution_root.symlink_to(Path(outside), target_is_directory=True)

            with self.assertRaises(PathBoundaryError):
                store.create_run("EVR-escape")
            with self.assertRaises(PathBoundaryError):
                store.append_text("EVR-existing", "report.md", "overwrite")
            with self.assertRaises(PathBoundaryError):
                store.read_text("EVR-existing", "report.md")

            self.assertFalse((Path(outside) / "runs" / "EVR-escape").exists())
            self.assertEqual(
                outside_report.read_text(encoding="utf-8"),
                "outside baseline",
            )

    def test_run_store_enforces_bounded_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = RepositoryEvolutionRunStore(Path(tempdir), read_limit=8)
            store.create_run("EVR-bounded")
            store.append_text("EVR-bounded", "report.md", "123456789")

            with self.assertRaisesRegex(ValueError, "exceeds read limit"):
                store.read_text("EVR-bounded", "report.md")

    def test_evolution_command_runner_bounds_stdout_and_stderr_with_receipts(self) -> None:
        script = (
            "import sys; "
            "sys.stdout.write('o' * 10000 + 'OUT-TAIL\\n'); "
            "sys.stderr.write('e' * 10000 + 'ERR-TAIL\\n')"
        )
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            receipt_path, results = RepositoryEvolutionCommandRunner(
                timeout_seconds=5,
                max_output_bytes=256,
            ).run(
                commands=(_evolution_command(command),),
                worktree_root=root,
                artifact_root=root / "artifacts",
                recorded_at="2026-07-20T00:00:00Z",
            )

            receipt = json.loads((root / receipt_path).read_text(encoding="utf-8"))
            stdout = (root / results[0].stdout_path).read_text(encoding="utf-8")
            stderr = (root / results[0].stderr_path).read_text(encoding="utf-8")

        self.assertEqual(results[0].status, "passed")
        self.assertFalse(results[0].timed_out)
        self.assertGreater(results[0].stdout_truncated_bytes, 0)
        self.assertGreater(results[0].stderr_truncated_bytes, 0)
        self.assertIn("OUT-TAIL", stdout)
        self.assertIn("ERR-TAIL", stderr)
        self.assertEqual(receipt["max_output_bytes"], 256)
        self.assertGreater(receipt["results"][0]["stdout_truncated_bytes"], 0)

    def test_evolution_command_runner_kills_timeout_and_records_failure(self) -> None:
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            marker = root / "child-survived.txt"
            child_script = (
                "import time; from pathlib import Path; time.sleep(0.5); "
                f"Path({str(marker)!r}).write_text('survived', encoding='utf-8')"
            )
            script = (
                "import subprocess, sys, time; "
                f"subprocess.Popen([sys.executable, '-c', {child_script!r}]); "
                "time.sleep(5)"
            )
            command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
            receipt_path, results = RepositoryEvolutionCommandRunner(
                timeout_seconds=0.1,
                max_output_bytes=256,
            ).run(
                commands=(_evolution_command(command),),
                worktree_root=root,
                artifact_root=root / "artifacts",
                recorded_at="2026-07-20T00:00:00Z",
            )
            receipt = json.loads((root / receipt_path).read_text(encoding="utf-8"))
            time.sleep(0.6)
            child_survived = marker.exists()

        self.assertLess(time.monotonic() - started, 2.0)
        self.assertFalse(child_survived)
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[0].exit_code, 124)
        self.assertTrue(results[0].timed_out)
        self.assertIn("timed out", results[0].error or "")
        self.assertTrue(receipt["results"][0]["timed_out"])


def _evolution_command(command: str) -> EvolutionWorktreeCommand:
    return EvolutionWorktreeCommand(
        source_task_id="TF-evolution-test",
        source="verify_command",
        original_command=command,
        normalized_command=command,
    )


if __name__ == "__main__":
    unittest.main()
