from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.application.results.inbox_handlers import (
    AdoptedChanges,
    PromotionMergeReceipt,
)
from sisyphus.application.results.task_creation import CreateOutcome
from sisyphus.application.use_cases.conversation import ConversationEventService
from sisyphus.application.use_cases.merge_events import PullRequestMergedEventService
from sisyphus.application.ports.workflow import WorkflowEvent


def task_record(*, slug: str = "example", status: str = "open") -> dict[str, object]:
    return {
        "id": f"TF-{slug}",
        "type": "feature",
        "slug": slug,
        "status": status,
        "stage": "plan_review",
        "plan_status": "pending_review",
        "spec_status": "draft",
        "branch": f"feat/{slug}",
        "base_branch": "main",
        "repo_root": "/repo",
        "task_dir": f".planning/tasks/TF-{slug}",
        "worktree_path": f"/worktrees/TF-{slug}",
        "docs": {"brief": "BRIEF.md", "plan": "PLAN.md", "log": "LOG.md"},
        "meta": {},
        "created_at": "2026-07-19T00:00:00Z",
        "updated_at": "2026-07-19T00:00:00Z",
    }


def conversation_event(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Create example",
        "message": "Implement the requested example",
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
    }
    payload.update(overrides)
    return {"id": "evt-fixed", "payload": payload}


class FakeTasks:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = {str(record["id"]): record for record in records}
        self.saved: list[dict[str, object]] = []

    def load(self, task_id: str) -> dict[str, object]:
        return self.records[task_id]

    def list(self) -> tuple[dict[str, object], ...]:
        return tuple(self.records.values())

    def save(self, task: dict[str, object]) -> None:
        self.records[str(task["id"])] = task
        self.saved.append(task)

    def update(self, task_id, mutator):
        task = self.load(task_id)
        result = mutator(task)
        self.save(result or task)
        return result or task


class FakeCreation:
    def __init__(self, tasks: FakeTasks) -> None:
        self.tasks = tasks
        self.commands = []

    def create(self, command) -> CreateOutcome:
        self.commands.append(command)
        task = task_record(slug=command.slug)
        self.tasks.records[str(task["id"])] = task
        return CreateOutcome(task=task, task_file=Path("/task.json"))


class FakeDocuments:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.materialized = []
        self.notes: list[str] = []

    def materialize(self, task, **kwargs) -> None:
        self.calls.append("documents")
        self.materialized.append((task, kwargs))

    def append_log_note(self, task, note: str) -> None:
        self.calls.append("log-note")
        self.notes.append(note)


class FakeAdoption:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def apply(self, *, worktree_root: Path, requested_paths: tuple[str, ...]):
        self.calls.append("adopt")
        return AdoptedChanges(
            source_branch="main",
            source_repo_root="/repo",
            paths=requested_paths,
            deleted_paths=(),
        )


class FakeGates:
    def __init__(self, tasks: FakeTasks, *, approved: bool, frozen: bool) -> None:
        self.tasks = tasks
        self.approved = approved
        self.frozen = frozen
        self.calls: list[str] = []

    def enforce_plan_approved(self, task_id: str, *, action: str):
        self.calls.append(f"plan:{action}")
        return self.approved, self.tasks.load(task_id)

    def enforce_spec_frozen(self, task_id: str, *, action: str):
        self.calls.append(f"spec:{action}")
        return self.frozen, self.tasks.load(task_id)


class FakeAgents:
    def __init__(self, calls: list[str], exit_code: int = 0) -> None:
        self.calls = calls
        self.exit_code = exit_code
        self.requests: list[dict[str, object]] = []

    def run(self, **kwargs) -> int:
        self.calls.append("agent")
        self.requests.append(kwargs)
        return self.exit_code


class FakeEvents:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.events: list[WorkflowEvent] = []

    def publish(self, event: WorkflowEvent) -> None:
        self.calls.append(f"event:{event.event_type}")
        self.events.append(event)


class FakeInterventions:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.requests = []

    def required(self, **kwargs) -> None:
        self.calls.append("intervention")
        self.requests.append(kwargs)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T01:02:03Z"


class ConversationEventApplicationTests(unittest.TestCase):
    def _service(
        self,
        *,
        existing: list[dict[str, object]] | None = None,
        approved: bool = False,
        frozen: bool = False,
    ):
        calls: list[str] = []
        tasks = FakeTasks(existing or [])
        creation = FakeCreation(tasks)
        documents = FakeDocuments(calls)
        adoption = FakeAdoption(calls)
        gates = FakeGates(tasks, approved=approved, frozen=frozen)
        agents = FakeAgents(calls)
        events = FakeEvents(calls)
        interventions = FakeInterventions(calls)
        service = ConversationEventService(
            tasks=tasks,
            creation=creation,
            documents=documents,
            adoption=adoption,
            gates=gates,
            agents=agents,
            events=events,
            interventions=interventions,
            clock=FixedClock(),
        )
        return service, tasks, creation, documents, gates, agents, events, calls

    def test_closed_duplicate_becomes_followup_and_persists_source_metadata(self) -> None:
        closed = task_record(slug="example", status="closed")
        service, tasks, creation, documents, _gates, agents, events, calls = self._service(
            existing=[closed]
        )

        result = service.process(
            conversation_event(source_context={"kind": "discord"})
        )

        self.assertEqual(creation.commands[0].slug, "example-followup")
        self.assertEqual(result["slug"], "example-followup")
        self.assertEqual(result["followup_of_task_id"], closed["id"])
        created = tasks.load(str(result["task_id"]))
        self.assertEqual(created["meta"]["source_event_id"], "evt-fixed")
        self.assertEqual(created["meta"]["source_context"], {"kind": "discord"})
        self.assertEqual(documents.materialized[0][1]["requested_slug"], "example")
        self.assertEqual(agents.requests, [])
        self.assertEqual(
            calls,
            ["documents", "event:task.created", "intervention"],
        )
        self.assertEqual(events.events[0].event_type, "task.created")

    def test_auto_run_stops_at_plan_gate_and_publishes_blocked_event(self) -> None:
        service, _tasks, _creation, _documents, gates, agents, events, _calls = (
            self._service(approved=False)
        )

        result = service.process(conversation_event(auto_run=True))

        self.assertFalse(result["auto_run"])
        self.assertEqual(result["blocked_reason"], "task plan must be approved before auto-run")
        self.assertEqual(gates.calls, ["plan:auto-run"])
        self.assertEqual(agents.requests, [])
        self.assertEqual(events.events[-1].event_type, "task.blocked")

    def test_adoption_and_agent_request_keep_order_and_arguments(self) -> None:
        service, tasks, _creation, documents, gates, agents, _events, calls = self._service(
            approved=True,
            frozen=True,
        )

        result = service.process(
            conversation_event(
                auto_run=True,
                adopt_current_changes=True,
                adopt_paths=["README.md"],
                owned_paths=["src"],
                provider_args=["--full-auto"],
                instruction="implement",
            )
        )

        self.assertTrue(result["auto_run"])
        self.assertEqual(gates.calls, ["plan:auto-run", "spec:auto-run"])
        self.assertEqual(agents.requests[0]["owned_paths"], ("src",))
        self.assertEqual(agents.requests[0]["provider_args"], ("--full-auto",))
        adopted = tasks.load(str(result["task_id"]))["meta"]["adopted_changes"]
        self.assertEqual(adopted["applied_at"], "2026-07-19T01:02:03Z")
        self.assertIn("Adopted 1 current changes", documents.notes[0])
        self.assertLess(calls.index("adopt"), calls.index("agent"))


class FakePromotionMerge:
    def __init__(self) -> None:
        self.commands = []

    def record(self, command) -> PromotionMergeReceipt:
        self.commands.append(command)
        return PromotionMergeReceipt(
            task_id="TF-example",
            branch="feat/example",
            pr_number=17,
            title="Merge example",
            recorded_at="2026-07-19T00:00:00Z",
            receipt_path="/repo/receipt.json",
            changeset_path="/repo/CHANGESET.md",
            close_attempted=True,
            closed=True,
            close_status="closed",
            close_gate_codes=(),
            child_retargeted_task_ids=("TF-child",),
        )


class PullRequestMergedEventApplicationTests(unittest.TestCase):
    def test_service_maps_payload_records_promotion_and_publishes_same_projection(self) -> None:
        calls: list[str] = []
        promotions = FakePromotionMerge()
        events = FakeEvents(calls)
        service = PullRequestMergedEventService(promotions=promotions, events=events)

        result = service.process(
            {
                "payload": {
                    "task_id": "TF-example",
                    "branch": "feat/example",
                    "repo_full_name": "jihkang/Sisyphus",
                    "pr_number": 17,
                    "title": "Merge example",
                    "url": None,
                    "base_branch": "main",
                    "head_branch": "feat/example",
                    "head_sha": None,
                    "merge_commit_sha": "abc123",
                    "merged_at": None,
                    "merged_by": None,
                    "merge_method": "squash",
                    "additions": 3,
                    "deletions": 1,
                    "changed_files": [{"path": "src/example.py"}],
                }
            }
        )

        self.assertEqual(promotions.commands[0].pr_number, 17)
        self.assertEqual(promotions.commands[0].changed_files, ({"path": "src/example.py"},))
        self.assertEqual(result["receipt_path"], "/repo/receipt.json")
        self.assertEqual(result["child_retargeted_task_ids"], ["TF-child"])
        self.assertEqual(events.events[0].event_type, "promotion.recorded")
        self.assertEqual(events.events[0].data["task_id"], result["task_id"])


if __name__ == "__main__":
    unittest.main()
