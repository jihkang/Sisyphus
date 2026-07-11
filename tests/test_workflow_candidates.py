from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.config import load_config
from sisyphus.domain.workflow.candidates import (
    WORKFLOW_CANDIDATE_INDEX_SCHEMA,
    is_workflow_candidate,
    list_workflow_candidate_ids,
)
from sisyphus.domain.workflow.service import run_workflow_cycle
from sisyphus.infra.persistence import read_json_file
from sisyphus.shared.paths import workflow_candidate_index_file


class WorkflowCandidateIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        self.task_dir_name = ".planning/tasks"
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_candidate_filter_matches_existing_early_return_guards(self) -> None:
        base = _task_record(self.repo_root, "TF-eligible")
        cases = [
            ("eligible", base, True),
            ("auto-disabled", {**base, "meta": {"auto_loop_enabled": False}}, False),
            ("closed", {**base, "status": "closed"}, False),
            ("needs-input", {**base, "workflow_phase": "needs_user_input"}, False),
            ("promotion", {**base, "workflow_phase": "promotion_pending"}, False),
            ("retarget", {**base, "workflow_phase": "retarget_required"}, False),
            ("plan-review", {**base, "plan_status": "pending_review"}, False),
        ]

        for label, task, expected in cases:
            with self.subTest(label=label):
                self.assertIs(is_workflow_candidate(task), expected)

    def test_candidates_are_deterministically_ordered_by_updated_at_then_id(self) -> None:
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-b", updated_at="2026-07-11T00:00:02Z"))
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-c", updated_at="2026-07-11T00:00:01Z"))
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-a", updated_at="2026-07-11T00:00:01Z"))
        _write_task(
            self.repo_root,
            _task_record(self.repo_root, "TF-closed", status="closed", workflow_phase="closed"),
        )

        candidates = list_workflow_candidate_ids(self.repo_root, self.task_dir_name)

        self.assertEqual(candidates, ["TF-a", "TF-c", "TF-b"])

    def test_warm_cycle_does_not_read_500_unchanged_closed_records(self) -> None:
        for index in range(500):
            task_id = f"TF-closed-{index:04d}"
            _write_task(
                self.repo_root,
                _task_record(self.repo_root, task_id, status="closed", workflow_phase="closed"),
            )
        with mock.patch(
            "sisyphus.domain.workflow.candidates.read_json_file",
            wraps=read_json_file,
        ) as cold_read_json:
            self.assertEqual(run_workflow_cycle(self.repo_root, self.config), 0)
        cold_task_reads = [
            call
            for call in cold_read_json.call_args_list
            if Path(call.args[0]).name == "task.json"
        ]
        self.assertEqual(len(cold_task_reads), 500)

        with mock.patch(
            "sisyphus.domain.workflow.candidates.read_json_file",
            wraps=read_json_file,
        ) as read_json:
            with mock.patch("sisyphus.domain.workflow.service._advance_task") as advance_task:
                progressed = run_workflow_cycle(self.repo_root, self.config)

        task_reads = [
            call
            for call in read_json.call_args_list
            if Path(call.args[0]).name == "task.json"
        ]
        self.assertEqual(progressed, 0)
        self.assertEqual(task_reads, [])
        self.assertEqual(read_json.call_count, 1)
        advance_task.assert_not_called()

    def test_new_changed_and_deleted_tasks_invalidate_only_their_entries(self) -> None:
        first = _task_record(
            self.repo_root,
            "TF-first",
            status="closed",
            workflow_phase="closed",
        )
        first_path = _write_task(self.repo_root, first)
        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), [])

        first["status"] = "open"
        first["workflow_phase"] = "execution"
        first["updated_at"] = "2026-07-11T00:00:02Z"
        _write_json(first_path, first)
        second = _task_record(self.repo_root, "TF-second", updated_at="2026-07-11T00:00:03Z")
        _write_task(self.repo_root, second)
        self.assertEqual(
            list_workflow_candidate_ids(self.repo_root, self.task_dir_name),
            ["TF-first", "TF-second"],
        )

        first_path.unlink()
        self.assertEqual(
            list_workflow_candidate_ids(self.repo_root, self.task_dir_name),
            ["TF-second"],
        )

    def test_malformed_task_is_skipped_until_its_fingerprint_changes(self) -> None:
        task_path = self.repo_root / self.task_dir_name / "TF-repaired" / "task.json"
        task_path.parent.mkdir(parents=True)
        task_path.write_text("{bad json\n", encoding="utf-8")

        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), [])

        _write_json(task_path, _task_record(self.repo_root, "TF-repaired"))
        self.assertEqual(
            list_workflow_candidate_ids(self.repo_root, self.task_dir_name),
            ["TF-repaired"],
        )

    def test_record_id_must_match_its_task_directory(self) -> None:
        task = _task_record(self.repo_root, "TF-directory")
        task["id"] = "../outside"
        task_path = self.repo_root / self.task_dir_name / "TF-directory" / "task.json"
        _write_json(task_path, task)

        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), [])

    def test_malformed_and_wrong_version_indexes_rebuild_from_task_files(self) -> None:
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-indexed"))
        index_path = workflow_candidate_index_file(self.repo_root)
        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), ["TF-indexed"])

        index_path.write_text("{bad json\n", encoding="utf-8")
        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), ["TF-indexed"])

        payload = json.loads(index_path.read_text(encoding="utf-8"))
        payload["schema_version"] = "sisyphus.workflow_candidate_index.v999"
        _write_json(index_path, payload)
        self.assertEqual(list_workflow_candidate_ids(self.repo_root, self.task_dir_name), ["TF-indexed"])
        rebuilt = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["schema_version"], WORKFLOW_CANDIDATE_INDEX_SCHEMA)

    def test_structurally_invalid_index_entry_forces_a_complete_rebuild(self) -> None:
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-valid"))
        index_path = workflow_candidate_index_file(self.repo_root)
        list_workflow_candidate_ids(self.repo_root, self.task_dir_name)
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        payload["entries"]["TF-valid/task.json"]["eligible"] = "yes"
        _write_json(index_path, payload)

        with mock.patch(
            "sisyphus.domain.workflow.candidates.read_json_file",
            wraps=read_json_file,
        ) as read_json:
            candidates = list_workflow_candidate_ids(self.repo_root, self.task_dir_name)

        task_reads = [call for call in read_json.call_args_list if Path(call.args[0]).name == "task.json"]
        self.assertEqual(candidates, ["TF-valid"])
        self.assertEqual(len(task_reads), 1)

    def test_unchanged_refresh_does_not_rewrite_index(self) -> None:
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-stable"))
        list_workflow_candidate_ids(self.repo_root, self.task_dir_name)

        with mock.patch("sisyphus.domain.workflow.candidates.write_json_file") as write_index:
            candidates = list_workflow_candidate_ids(self.repo_root, self.task_dir_name)

        self.assertEqual(candidates, ["TF-stable"])
        write_index.assert_not_called()

    def test_cache_write_failure_does_not_block_candidate_selection(self) -> None:
        _write_task(self.repo_root, _task_record(self.repo_root, "TF-no-cache"))

        with mock.patch(
            "sisyphus.domain.workflow.candidates.write_json_file",
            side_effect=PermissionError("read-only cache"),
        ):
            candidates = list_workflow_candidate_ids(self.repo_root, self.task_dir_name)

        self.assertEqual(candidates, ["TF-no-cache"])

    def test_workflow_cycle_advances_only_indexed_candidates_in_order(self) -> None:
        with mock.patch(
            "sisyphus.domain.workflow.service.list_workflow_candidate_ids",
            return_value=["TF-first", "TF-second"],
        ) as list_candidates:
            with mock.patch(
                "sisyphus.domain.workflow.service._advance_task",
                side_effect=[True, False],
            ) as advance_task:
                progressed = run_workflow_cycle(self.repo_root, self.config)

        self.assertEqual(progressed, 1)
        list_candidates.assert_called_once_with(
            repo_root=self.repo_root,
            task_dir_name=self.config.task_dir,
        )
        self.assertEqual(
            [call.kwargs["task_id"] for call in advance_task.call_args_list],
            ["TF-first", "TF-second"],
        )


def _task_record(
    repo_root: Path,
    task_id: str,
    *,
    status: str = "open",
    workflow_phase: str = "execution",
    updated_at: str = "2026-07-11T00:00:00Z",
) -> dict[str, object]:
    return {
        "id": task_id,
        "type": "feature",
        "slug": task_id.lower(),
        "status": status,
        "stage": "execution",
        "plan_status": "approved",
        "spec_status": "frozen",
        "workflow_phase": workflow_phase,
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": updated_at,
        "repo_root": str(repo_root),
        "task_dir": f".planning/tasks/{task_id}",
        "worktree_path": "",
        "branch": f"feat/{task_id.lower()}",
        "base_branch": "main",
        "meta": {"auto_loop_enabled": True},
    }


def _write_task(repo_root: Path, task: dict[str, object]) -> Path:
    task_id = str(task["id"])
    task_path = repo_root / ".planning" / "tasks" / task_id / "task.json"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(task_path, task)
    return task_path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
