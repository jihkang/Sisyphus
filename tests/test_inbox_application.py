from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.application.commands.inbox import QueueConversationCommand
from sisyphus.application.results.inbox import DaemonStats
from sisyphus.application.use_cases.daemon_loop import DaemonLoopService
from sisyphus.application.use_cases.inbox import InboxQueueService
from sisyphus.application.use_cases.inbox_processing import InboxProcessingService
from sisyphus.application.ports.workflow import WorkflowEvent
from sisyphus.domain.inbox import InboxValidationError
from sisyphus.infra.daemon.event_log import JsonlDaemonEventLog


class FakeClock:
    def __init__(self) -> None:
        self.counter = 0

    def now(self) -> str:
        self.counter += 1
        return f"2026-07-19T00:00:{self.counter:02d}Z"


class FakeEventLog:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.entries: list[dict[str, object]] = []

    def append(self, entry) -> None:
        self.calls.append(f"log:{entry['status']}")
        self.entries.append(dict(entry))


class FakeEvents:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.events: list[WorkflowEvent] = []

    def publish(self, event: WorkflowEvent) -> None:
        self.calls.append(f"publish:{event.event_type}")
        self.events.append(event)


class FakeInbox:
    def __init__(self, calls: list[str], raw: object | Exception | None = None) -> None:
        self.calls = calls
        self.raw = raw
        self.available: list[Path] = []
        self.enqueued: list[dict[str, object]] = []
        self.completed: list[dict[str, object]] = []
        self.failed: list[dict[str, object]] = []

    def enqueue(self, event: dict[str, object]) -> Path:
        self.calls.append("enqueue")
        self.enqueued.append(event)
        return Path(f"/pending/{event['id']}.json")

    def list_processable(self) -> list[Path]:
        self.calls.append("list")
        result, self.available = self.available, []
        return result

    def claim(self, event_path: Path) -> Path:
        self.calls.append("claim")
        return Path("/processing") / event_path.name

    def read(self, event_path: Path) -> object:
        self.calls.append("read")
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw

    def update(self, event_path: Path, event: dict[str, object]) -> None:
        self.calls.append(f"update:{event['status']}")

    def complete(self, event_path: Path, event: dict[str, object]) -> Path:
        self.calls.append("complete")
        self.completed.append(dict(event))
        return Path("/processed") / event_path.name

    def fail(self, event_path: Path, event: dict[str, object]) -> Path:
        self.calls.append("fail")
        self.failed.append(dict(event))
        return Path("/failed") / event_path.name


def valid_conversation_event() -> dict[str, object]:
    return {
        "id": "evt-fixed",
        "event_type": "conversation",
        "status": "queued",
        "created_at": "2026-07-19T00:00:01Z",
        "updated_at": "2026-07-19T00:00:02Z",
        "payload": {
            "title": "Example",
            "message": "Create an example",
            "task_type": "feature",
            "slug": "example",
            "instruction": None,
            "agent_id": "worker-1",
            "role": "worker",
            "provider": "codex",
            "owned_paths": [],
            "provider_args": [],
            "source_context": {},
            "adopt_current_changes": False,
            "adopt_paths": [],
            "auto_run": False,
        },
        "result": None,
        "error": None,
    }


class InboxQueueApplicationTests(unittest.TestCase):
    def test_queue_validates_before_persistence_and_preserves_effect_order(self) -> None:
        calls: list[str] = []
        inbox = FakeInbox(calls)
        event_log = FakeEventLog(calls)
        events = FakeEvents(calls)

        def parse(raw: object) -> dict[str, object]:
            calls.append("parse")
            return dict(raw)  # type: ignore[arg-type]

        service = InboxQueueService(
            inbox=inbox,
            parse_event=parse,
            event_log=event_log,
            events=events,
            clock=FakeClock(),
            new_event_id=lambda: "evt-fixed",
        )

        event, path = service.queue_conversation(
            QueueConversationCommand(
                message="Create inbox boundaries",
                auto_run=False,
            )
        )

        self.assertEqual(event["payload"]["title"], "Create inbox boundaries")
        self.assertEqual(event["payload"]["slug"], "create-inbox-boundaries")
        self.assertEqual(path, Path("/pending/evt-fixed.json"))
        self.assertEqual(
            calls,
            ["parse", "enqueue", "log:queued", "publish:conversation.queued"],
        )

    def test_queue_maps_validation_error_to_daemon_error(self) -> None:
        from sisyphus.application.use_cases.inbox import DaemonError

        calls: list[str] = []
        service = InboxQueueService(
            inbox=FakeInbox(calls),
            parse_event=lambda raw: (_ for _ in ()).throw(
                InboxValidationError("invalid_value", "payload.message", "must not be empty")
            ),
            event_log=FakeEventLog(calls),
            events=FakeEvents(calls),
            clock=FakeClock(),
            new_event_id=lambda: "evt-fixed",
        )

        with self.assertRaisesRegex(DaemonError, "payload.message"):
            service.queue_conversation(QueueConversationCommand(message=""))

        self.assertNotIn("enqueue", calls)


class InboxProcessingApplicationTests(unittest.TestCase):
    def _service(
        self,
        *,
        raw: object | Exception,
        handler,
    ) -> tuple[InboxProcessingService, FakeInbox, FakeEventLog, FakeEvents, list[str]]:
        calls: list[str] = []
        inbox = FakeInbox(calls, raw=raw)
        event_log = FakeEventLog(calls)
        events = FakeEvents(calls)

        def parse(value: object) -> dict[str, object]:
            calls.append("parse")
            return dict(value)  # type: ignore[arg-type]

        service = InboxProcessingService(
            inbox=inbox,
            parse_event=parse,
            handlers={"conversation": handler},
            event_log=event_log,
            events=events,
            clock=FakeClock(),
        )
        return service, inbox, event_log, events, calls

    def test_process_commits_success_only_after_handler_and_event_publish(self) -> None:
        def handler(event: dict[str, object]) -> dict[str, object]:
            calls.append("handler")
            return {"task_id": "TF-created"}

        service, inbox, _event_log, _events, calls = self._service(
            raw=valid_conversation_event(),
            handler=handler,
        )
        stats = DaemonStats()

        result = service.process(Path("/pending/evt-fixed.json"), stats=stats)

        self.assertEqual(result["status"], "processed")
        self.assertEqual(stats.processed, 1)
        self.assertEqual(len(inbox.completed), 1)
        self.assertEqual(
            calls,
            [
                "claim",
                "read",
                "parse",
                "update:processing",
                "log:processing",
                "handler",
                "log:processed",
                "publish:conversation.processed",
                "complete",
            ],
        )

    def test_handler_failure_moves_claimed_event_to_failed(self) -> None:
        service, inbox, _event_log, events, _calls = self._service(
            raw=valid_conversation_event(),
            handler=lambda event: (_ for _ in ()).throw(RuntimeError("provider failed")),
        )
        stats = DaemonStats()

        result = service.process(Path("/pending/evt-fixed.json"), stats=stats)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "provider failed")
        self.assertEqual(stats.failed, 1)
        self.assertEqual(len(inbox.failed), 1)
        self.assertEqual(events.events[-1].event_type, "conversation.failed")

    def test_invalid_json_is_normalized_and_quarantined(self) -> None:
        malformed = json.JSONDecodeError("bad json", "{", 1)
        service, inbox, _event_log, events, _calls = self._service(
            raw=malformed,
            handler=lambda event: {"task_id": "unreachable"},
        )

        result = service.process(Path("/pending/bad.json"))

        self.assertEqual(result["id"], "bad")
        self.assertTrue(str(result["error"]).startswith("invalid_json:"))
        self.assertEqual(len(inbox.failed), 1)
        self.assertEqual(events.events[-1].event_type, "inbox.event.failed")


class DaemonLoopApplicationTests(unittest.TestCase):
    def test_loop_skips_claim_race_then_runs_workflow_until_quiescent(self) -> None:
        calls: list[str] = []
        inbox = FakeInbox(calls)
        inbox.available = [Path("/pending/raced.json"), Path("/pending/valid.json")]

        def process(path: Path, stats: DaemonStats) -> dict[str, object]:
            calls.append(f"process:{path.stem}")
            if path.stem == "raced":
                raise FileNotFoundError(path)
            stats.processed += 1
            return {}

        workflow_results = iter((1, 0))
        service = DaemonLoopService(
            inbox=inbox,
            process_event=process,
            workflow_cycle=lambda: next(workflow_results),
            sleep=lambda seconds: calls.append(f"sleep:{seconds}"),
        )

        stats = service.run(once=True, poll_interval_seconds=1)

        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.processed, 1)
        self.assertEqual(stats.orchestrated, 1)
        self.assertNotIn("sleep:1", calls)


class JsonlDaemonEventLogTests(unittest.TestCase):
    def test_adapter_uses_the_locked_fsyncing_jsonl_append_primitive(self) -> None:
        path = Path("/repo/.planning/events.jsonl")
        log = JsonlDaemonEventLog(Path("/repo"))

        with mock.patch(
            "sisyphus.infra.daemon.event_log.append_jsonl_text"
        ) as append_jsonl:
            log.append({"status": "processed", "event_id": "evt-fixed"})

        append_jsonl.assert_called_once()
        self.assertEqual(append_jsonl.call_args.args[0], path)
        self.assertEqual(
            json.loads(append_jsonl.call_args.args[1]),
            {"status": "processed", "event_id": "evt-fixed"},
        )


if __name__ == "__main__":
    unittest.main()
