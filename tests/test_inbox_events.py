from __future__ import annotations

import copy
import json
import math
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
from sisyphus.daemon import (
    DaemonError,
    DaemonStats,
    _render_brief,
    _render_feature_plan,
    _render_issue_fix_plan,
    _render_issue_repro,
    process_inbox_event,
    queue_conversation_event,
    run_daemon,
)
from sisyphus.domain.inbox import InboxEvent, InboxValidationError
from sisyphus.domain.inbox.models import MAX_LIST_ITEMS, MAX_MESSAGE_LENGTH
from sisyphus.domain.task.documents import (
    render_brief,
    render_feature_plan,
    render_issue_fix_plan,
    render_issue_repro,
)
from sisyphus.infra.persistence.inbox import InboxRepository, write_json_file
from sisyphus.interfaces.inbox import inbox_event_to_record, parse_inbox_event
from sisyphus.shared.paths import (
    inbox_failed_dir,
    inbox_pending_dir,
    inbox_processed_dir,
    inbox_processing_dir,
)


def conversation_event() -> dict[str, object]:
    return {
        "id": "evt-123456789abc",
        "event_type": "conversation",
        "status": "queued",
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:00:01Z",
        "payload": {
            "title": "Add inbox validation",
            "message": "Validate every queued event",
            "task_type": "feature",
            "slug": "add-inbox-validation",
            "instruction": None,
            "agent_id": "worker-1",
            "role": "worker",
            "provider": "codex",
            "owned_paths": ["src/sisyphus/daemon.py"],
            "provider_args": ["--full-auto"],
            "source_context": {"kind": "test", "sequence": 1, "flags": [True, None]},
            "adopt_current_changes": False,
            "adopt_paths": ["README.md"],
            "auto_run": False,
        },
        "result": None,
        "error": None,
    }


def pull_request_event() -> dict[str, object]:
    return {
        "id": "evt-abcdef123456",
        "event_type": "pull_request_merged",
        "status": "queued",
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:00:01Z",
        "payload": {
            "task_id": "TF-20260711-feature-demo",
            "branch": "feat/demo",
            "repo_full_name": "jihkang/Sisyphus",
            "pr_number": 57,
            "title": "Merge demo",
            "url": "https://github.com/jihkang/Sisyphus/pull/57",
            "base_branch": "main",
            "head_branch": "feat/demo",
            "head_sha": "a" * 40,
            "merge_commit_sha": "b" * 40,
            "merged_at": "2026-07-11T00:00:00Z",
            "merged_by": "jihkang",
            "merge_method": "squash",
            "additions": 10,
            "deletions": 2,
            "changed_files": [
                {
                    "path": "src/sisyphus/daemon.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 2,
                }
            ],
        },
        "result": None,
        "error": None,
    }


class InboxEventModelTests(unittest.TestCase):
    def test_domain_event_does_not_own_boundary_serialization(self) -> None:
        self.assertFalse(hasattr(InboxEvent, "from_dict"))
        self.assertFalse(hasattr(InboxEvent, "to_dict"))

    def test_conversation_round_trip_preserves_current_shape(self) -> None:
        raw = conversation_event()

        self.assertEqual(inbox_event_to_record(parse_inbox_event(raw)), raw)

    def test_pull_request_round_trip_preserves_current_shape(self) -> None:
        raw = pull_request_event()

        self.assertEqual(inbox_event_to_record(parse_inbox_event(raw)), raw)

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        unknown = conversation_event()
        unknown["unexpected"] = True
        missing = conversation_event()
        del missing["payload"]
        unknown_payload = conversation_event()
        unknown_payload["payload"]["unexpected"] = True

        for raw in (unknown, missing, unknown_payload):
            with self.subTest(raw=raw):
                with self.assertRaises(InboxValidationError):
                    parse_inbox_event(raw)

    def test_exact_scalar_and_container_types_are_enforced(self) -> None:
        cases: list[tuple[str, dict[str, object]]] = []
        wrong_message = conversation_event()
        wrong_message["payload"]["message"] = 1
        cases.append(("message", wrong_message))
        wrong_boolean = conversation_event()
        wrong_boolean["payload"]["auto_run"] = 1
        cases.append(("boolean", wrong_boolean))
        wrong_list = conversation_event()
        wrong_list["payload"]["owned_paths"] = ("src/sisyphus",)
        cases.append(("list", wrong_list))
        boolean_integer = pull_request_event()
        boolean_integer["payload"]["pr_number"] = True
        cases.append(("integer", boolean_integer))

        for label, raw in cases:
            with self.subTest(label=label):
                with self.assertRaises(InboxValidationError):
                    parse_inbox_event(raw)

    def test_bounded_strings_and_collections_are_enforced(self) -> None:
        oversized_message = conversation_event()
        oversized_message["payload"]["message"] = "x" * (MAX_MESSAGE_LENGTH + 1)
        oversized_list = conversation_event()
        oversized_list["payload"]["provider_args"] = ["x"] * (MAX_LIST_ITEMS + 1)

        for raw in (oversized_message, oversized_list):
            with self.subTest(kind="bounded"):
                with self.assertRaises(InboxValidationError) as raised:
                    parse_inbox_event(raw)
                self.assertEqual(raised.exception.code, "value_too_large")

    def test_unsafe_repository_paths_are_rejected(self) -> None:
        owned_path = conversation_event()
        owned_path["payload"]["owned_paths"] = ["../secrets.txt"]
        changed_file = pull_request_event()
        changed_file["payload"]["changed_files"][0]["path"] = "/tmp/escape.py"

        for raw in (owned_path, changed_file):
            with self.subTest(kind="path"):
                with self.assertRaises(InboxValidationError) as raised:
                    parse_inbox_event(raw)
                self.assertEqual(raised.exception.code, "unsafe_path")

    def test_source_context_must_be_strict_json(self) -> None:
        unsupported = conversation_event()
        unsupported["payload"]["source_context"] = {"bad": object()}
        non_finite = conversation_event()
        non_finite["payload"]["source_context"] = {"bad": math.inf}

        for raw in (unsupported, non_finite):
            with self.subTest(kind="json"):
                with self.assertRaises(InboxValidationError):
                    parse_inbox_event(raw)

    def test_merge_counts_must_be_non_negative(self) -> None:
        raw = pull_request_event()
        raw["payload"]["changed_files"][0]["deletions"] = -1

        with self.assertRaises(InboxValidationError) as raised:
            parse_inbox_event(raw)

        self.assertEqual(raised.exception.code, "invalid_value")


class InboxRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        self.repository = InboxRepository(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_enqueue_delegates_to_atomic_json_store(self) -> None:
        event = conversation_event()

        with mock.patch(
            "sisyphus.infra.persistence.inbox.write_json_file",
            wraps=write_json_file,
        ) as write_json:
            event_path = self.repository.enqueue(event)

        write_json.assert_called_once_with(event_path, event)
        self.assertEqual(event_path.parent, inbox_pending_dir(self.repo_root))
        self.assertEqual(json.loads(event_path.read_text(encoding="utf-8")), event)
        self.assertFalse(list(event_path.parent.glob("*.tmp")))

    def test_claim_and_complete_use_distinct_lifecycle_directories(self) -> None:
        event = conversation_event()
        pending = self.repository.enqueue(event)

        processing = self.repository.claim(pending)
        event["status"] = "processed"
        destination = self.repository.complete(processing, event)

        self.assertFalse(pending.exists())
        self.assertFalse(processing.exists())
        self.assertEqual(destination.parent, inbox_processed_dir(self.repo_root))
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["status"], "processed")

    def test_processing_files_are_recovered_before_pending_files(self) -> None:
        pending = self.repository.enqueue(conversation_event())
        processing = self.repository.claim(pending)
        later = copy.deepcopy(conversation_event())
        later["id"] = "evt-ffffffffffff"
        pending_later = self.repository.enqueue(later)

        self.assertEqual(self.repository.list_processable(), [processing, pending_later])


class InboxDaemonIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_pending(self, name: str, content: str) -> Path:
        event_path = inbox_pending_dir(self.repo_root) / name
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(content, encoding="utf-8")
        return event_path

    def test_malformed_json_is_quarantined_without_raising(self) -> None:
        event_path = self._write_pending("000-invalid.json", "{not json\n")
        stats = DaemonStats()

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
            stats=stats,
        )

        self.assertEqual(event["status"], "failed")
        self.assertTrue(str(event["error"]).startswith("invalid_json:"))
        self.assertEqual(stats.failed, 1)
        self.assertFalse(event_path.exists())
        failed = inbox_failed_dir(self.repo_root) / event_path.name
        self.assertEqual(json.loads(failed.read_text(encoding="utf-8"))["status"], "failed")

    def test_invalid_schema_and_unsupported_type_are_quarantined(self) -> None:
        invalid_schema = conversation_event()
        invalid_schema["payload"]["message"] = 3
        unsupported = conversation_event()
        unsupported["event_type"] = "heartbeat"

        for index, (raw, prefix) in enumerate(
            ((invalid_schema, "invalid_schema:"), (unsupported, "unsupported_event_type:"))
        ):
            with self.subTest(prefix=prefix):
                path = self._write_pending(f"00{index}-invalid.json", json.dumps(raw))
                event = process_inbox_event(
                    repo_root=self.repo_root,
                    config=self.config,
                    event_path=path,
                )
                self.assertEqual(event["status"], "failed")
                self.assertTrue(str(event["error"]).startswith(prefix))
                self.assertTrue((inbox_failed_dir(self.repo_root) / path.name).exists())

    def test_daemon_continues_with_valid_event_after_bad_event(self) -> None:
        self._write_pending("000-invalid.json", "[")
        queue_conversation_event(
            self.repo_root,
            title="Continue after invalid input",
            message="Process this valid event",
            auto_run=False,
        )

        with mock.patch(
            "sisyphus.daemon._process_conversation_event",
            return_value={"task_id": "TF-valid"},
        ) as process_valid:
            with mock.patch("sisyphus.daemon.run_workflow_cycle", return_value=0):
                stats = run_daemon(
                    repo_root=self.repo_root,
                    config=self.config,
                    once=True,
                    poll_interval_seconds=1,
                )

        self.assertEqual(stats.failed, 1)
        self.assertEqual(stats.processed, 1)
        process_valid.assert_called_once()
        self.assertEqual(len(list(inbox_failed_dir(self.repo_root).glob("*.json"))), 1)
        self.assertEqual(len(list(inbox_processed_dir(self.repo_root).glob("*.json"))), 1)
        self.assertFalse(list(inbox_pending_dir(self.repo_root).glob("*.json")))
        self.assertFalse(list(inbox_processing_dir(self.repo_root).glob("*.json")))

    def test_queue_validation_keeps_daemon_error_api(self) -> None:
        with self.assertRaises(DaemonError):
            queue_conversation_event(self.repo_root, message="", auto_run=False)

    def test_daemon_renderer_imports_are_compatibility_aliases(self) -> None:
        self.assertIs(_render_brief, render_brief)
        self.assertIs(_render_feature_plan, render_feature_plan)
        self.assertIs(_render_issue_repro, render_issue_repro)
        self.assertIs(_render_issue_fix_plan, render_issue_fix_plan)


if __name__ == "__main__":
    unittest.main()
