from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ...shared.mappings import project_fields
from ..commands.task import CreateTaskRecordCommand
from ..ports.clock import ClockPort
from ..ports.inbox_handlers import (
    ChangeAdoptionPort,
    ConversationAgentPort,
    ConversationDocumentPort,
    TaskExecutionGatePort,
)
from ..ports.task_creation import TaskCreationPort
from ..ports.workflow import (
    EventPublisherPort,
    ManualInterventionPort,
    TaskRecord,
    TaskRecordPort,
    WorkflowEvent,
)
from .inbox import DaemonError


CONVERSATION_FIELD_DEFAULTS = {
    "title": "",
    "message": "",
    "task_type": "feature",
    "slug": "",
    "instruction": None,
    "agent_id": "worker-1",
    "role": "worker",
    "provider": "codex",
    "owned_paths": list,
    "provider_args": list,
    "source_context": dict,
    "adopt_current_changes": False,
    "adopt_paths": list,
    "auto_run": True,
}


@dataclass(slots=True)
class ConversationEventService:
    tasks: TaskRecordPort
    creation: TaskCreationPort
    documents: ConversationDocumentPort
    adoption: ChangeAdoptionPort
    gates: TaskExecutionGatePort
    agents: ConversationAgentPort
    events: EventPublisherPort
    interventions: ManualInterventionPort
    clock: ClockPort

    def process(self, event: dict[str, object]) -> dict[str, object]:
        payload = project_fields(event.get("payload", {}), CONVERSATION_FIELD_DEFAULTS)
        title = str(payload["title"]).strip()
        message = str(payload["message"]).strip()
        task_type = str(payload["task_type"]).strip()
        requested_slug = str(payload["slug"]).strip() or _slugify(
            title or message,
            fallback=f"conversation-task-{str(event['id'])[-4:]}",
        )
        slug, parent_task_id = self._resolve_followup_slug(
            task_type=task_type,
            requested_slug=requested_slug,
        )
        provider = str(payload["provider"]).strip() or "codex"
        role = str(payload["role"]).strip() or "worker"
        instruction = payload["instruction"]
        agent_id = str(payload["agent_id"]).strip() or "worker-1"
        owned_paths = tuple(str(path) for path in payload["owned_paths"])
        provider_args = tuple(str(arg) for arg in payload["provider_args"])
        source_context = dict(payload["source_context"])
        adopt_current_changes = bool(payload["adopt_current_changes"])
        requested_adopt_paths = tuple(str(path) for path in payload["adopt_paths"])
        auto_run = bool(payload["auto_run"])
        requested_auto_run = auto_run

        outcome = self.creation.create(
            CreateTaskRecordCommand(
                task_type=task_type,
                slug=slug,
                spec_validation_required=True,
            )
        )
        task = outcome.task
        self.documents.materialize(
            task,
            title=title,
            message=message,
            requested_slug=requested_slug,
            parent_task_id=parent_task_id,
        )
        self._persist_conversation_metadata(
            task,
            event_id=str(event["id"]),
            provider=provider,
            auto_loop_enabled=requested_auto_run,
            source_context=source_context,
            owned_paths=owned_paths,
            requested_adopt_paths=requested_adopt_paths,
            requested_slug=requested_slug,
            parent_task_id=parent_task_id,
        )
        if adopt_current_changes:
            task = self._adopt_current_changes(
                task,
                requested_paths=requested_adopt_paths,
            )

        self.events.publish(
            WorkflowEvent(
                event_type="task.created",
                source={"module": "daemon"},
                data={
                    "task_id": task["id"],
                    "task_type": task["type"],
                    "slug": task["slug"],
                    "branch": task["branch"],
                    "worktree_path": task["worktree_path"],
                },
            )
        )
        self.interventions.required(
            task_id=str(task["id"]),
            reason="plan_review_required",
            workflow_phase="plan_in_review",
            status=str(task.get("status") or ""),
            detail="new task creation starts in plan review",
        )

        agent_exit_code: int | None = None
        blocked_reason: str | None = None
        if auto_run:
            approved, task = self.gates.enforce_plan_approved(
                str(task["id"]),
                action="auto-run",
            )
            if approved:
                frozen, task = self.gates.enforce_spec_frozen(
                    str(task["id"]),
                    action="auto-run",
                )
                if frozen:
                    agent_exit_code = self.agents.run(
                        provider=provider,
                        task_id=str(task["id"]),
                        agent_id=agent_id,
                        role=role,
                        instruction=str(instruction) if instruction else None,
                        owned_paths=owned_paths,
                        provider_args=provider_args,
                    )
                    if agent_exit_code != 0:
                        raise DaemonError(
                            f"{provider} worker exited with code {agent_exit_code}"
                        )
                else:
                    auto_run = False
                    blocked_reason = "task spec must be frozen before auto-run"
            else:
                auto_run = False
                blocked_reason = "task plan must be approved before auto-run"

        if blocked_reason:
            self.events.publish(
                WorkflowEvent(
                    event_type="task.blocked",
                    source={"module": "daemon"},
                    data={"task_id": task["id"], "reason": blocked_reason},
                )
            )

        return {
            "task_id": task["id"],
            "task_type": task["type"],
            "slug": task["slug"],
            "requested_slug": requested_slug,
            "followup_of_task_id": parent_task_id,
            "branch": task["branch"],
            "worktree_path": task["worktree_path"],
            "agent_id": agent_id if auto_run else None,
            "agent_exit_code": agent_exit_code,
            "auto_run": auto_run,
            "plan_status": task.get("plan_status"),
            "spec_status": task.get("spec_status"),
            "blocked_reason": blocked_reason,
        }

    def _persist_conversation_metadata(
        self,
        task: TaskRecord,
        *,
        event_id: str,
        provider: str,
        auto_loop_enabled: bool,
        source_context: dict[str, object],
        owned_paths: tuple[str, ...],
        requested_adopt_paths: tuple[str, ...],
        requested_slug: str,
        parent_task_id: str | None,
    ) -> None:
        task_record = self.tasks.load(str(task["id"]))
        task_record.setdefault("meta", {})
        task_record["meta"]["source_event_id"] = event_id
        task_record["meta"]["source_event_type"] = "conversation"
        task_record["meta"]["default_provider"] = provider
        task_record["meta"]["auto_loop_enabled"] = auto_loop_enabled
        task_record["meta"]["requested_slug"] = requested_slug
        task_record["meta"]["owned_paths"] = list(owned_paths)
        task_record["meta"]["requested_adopt_paths"] = list(requested_adopt_paths)
        if parent_task_id:
            task_record["meta"]["followup_of_task_id"] = parent_task_id
        if source_context:
            task_record["meta"]["source_context"] = source_context
        self.tasks.save(task_record)

    def _adopt_current_changes(
        self,
        task: TaskRecord,
        *,
        requested_paths: tuple[str, ...],
    ) -> TaskRecord:
        task_record = self.tasks.load(str(task["id"]))
        adopted = self.adoption.apply(
            worktree_root=Path(str(task_record["worktree_path"])),
            requested_paths=requested_paths,
        )
        task_record.setdefault("meta", {})
        task_record["meta"]["adopted_changes"] = {
            "source_branch": adopted.source_branch,
            "source_repo_root": adopted.source_repo_root,
            "paths": list(adopted.paths),
            "requested_paths": list(requested_paths),
            "deleted_paths": list(adopted.deleted_paths),
            "applied_at": self.clock.now(),
        }
        self.tasks.save(task_record)
        self.documents.append_log_note(
            task_record,
            _render_adoption_log_note(
                source_branch=adopted.source_branch,
                adopted_paths=adopted.paths,
                deleted_paths=adopted.deleted_paths,
            ),
        )
        return self.tasks.load(str(task["id"]))

    def _resolve_followup_slug(
        self,
        *,
        task_type: str,
        requested_slug: str,
    ) -> tuple[str, str | None]:
        tasks = tuple(self.tasks.list())
        matching = [
            task
            for task in tasks
            if str(task.get("type")) == task_type
            and str(task.get("slug")) == requested_slug
        ]
        if not matching:
            return requested_slug, None

        latest = sorted(
            matching,
            key=lambda task: (
                str(task.get("updated_at", "")),
                str(task.get("created_at", "")),
                str(task.get("id", "")),
            ),
        )[-1]
        if str(latest.get("status")) != "closed":
            return requested_slug, None

        sibling_slugs = {
            str(task.get("slug"))
            for task in tasks
            if str(task.get("type")) == task_type
        }
        return _next_followup_slug(requested_slug, sibling_slugs), str(latest.get("id"))


def _next_followup_slug(requested_slug: str, sibling_slugs: set[str]) -> str:
    base = f"{requested_slug}-followup"
    if base not in sibling_slugs:
        return base

    index = 2
    while True:
        candidate = f"{base}-{index}"
        if candidate not in sibling_slugs:
            return candidate
        index += 1


def _render_adoption_log_note(
    *,
    source_branch: str | None,
    adopted_paths: tuple[str, ...],
    deleted_paths: tuple[str, ...],
) -> str:
    branch_label = source_branch or "detached"
    path_count = len(adopted_paths)
    deleted_count = len(deleted_paths)
    if deleted_count:
        return (
            f"Adopted {path_count} current changes from branch `{branch_label}` into "
            f"the task worktree, including {deleted_count} deletions."
        )
    return (
        f"Adopted {path_count} current changes from branch `{branch_label}` into "
        "the task worktree."
    )


def _slugify(value: str, *, fallback: str = "conversation-task") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or fallback


__all__ = ["ConversationEventService"]
