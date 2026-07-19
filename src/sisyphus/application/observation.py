from __future__ import annotations

from collections.abc import Mapping

from .conformance_records import summarize_task_conformance
from ..domain.promotion.state import promotion_summary
from ..shared.digests import stable_json_hash


OBSERVATION_SCHEMA_VERSION = "sisyphus.task_observation.v1"


def project_task_observation(
    task: dict,
    *,
    required_docs: Mapping[str, str],
    evidence_summary: Mapping[str, object],
    allowed_next_actions: tuple[str, ...],
    forbidden_next_actions: tuple[dict[str, object], ...],
) -> dict[str, object]:
    conformance = summarize_task_conformance(task)
    gates = list(task.get("gates", [])) if isinstance(task.get("gates"), list) else []
    observation: dict[str, object] = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "task_id": task.get("id"),
        "type": task.get("type"),
        "slug": task.get("slug"),
        "phase": task.get("workflow_phase"),
        "status": task.get("status"),
        "stage": task.get("stage"),
        "plan_status": task.get("plan_status"),
        "spec_status": task.get("spec_status"),
        "verification": {
            "status": task.get("verify_status"),
            "last_verified_at": task.get("last_verified_at"),
            "audit_attempts": task.get("audit_attempts"),
            "max_audit_attempts": task.get("max_audit_attempts"),
            "last_result_count": len(task.get("last_verify_results", []))
            if isinstance(task.get("last_verify_results"), list)
            else 0,
        },
        "conformance": {
            "status": conformance.get("status"),
            "drift_count": conformance.get("drift_count"),
            "unresolved_warning_count": conformance.get("unresolved_warning_count"),
            "last_checkpoint_type": conformance.get("last_checkpoint_type"),
            "last_checkpoint_at": conformance.get("last_checkpoint_at"),
            "latest_warning": conformance.get("last_warning"),
            "latest_failure": conformance.get("last_failure"),
            "summary": conformance.get("summary"),
        },
        "gates": gates,
        "required_docs": dict(required_docs),
        "subtasks": _subtask_summary(task),
        "evidence_summary": dict(evidence_summary),
        "promotion": _promotion_observation(task),
        "allowed_next_actions": list(allowed_next_actions),
        "forbidden_next_actions": list(forbidden_next_actions),
        "reason": _reason(task, gates, conformance),
    }
    observation["observation_hash"] = stable_json_hash(observation)
    return observation


def _subtask_summary(task: dict) -> dict[str, int]:
    subtasks = task.get("subtasks", [])
    if not isinstance(subtasks, list):
        subtasks = []
    completed = sum(
        1 for item in subtasks if isinstance(item, dict) and item.get("status") == "completed"
    )
    blocked = sum(
        1
        for item in subtasks
        if isinstance(item, dict) and item.get("status") in {"blocked", "failed"}
    )
    queued = sum(
        1 for item in subtasks if isinstance(item, dict) and item.get("status") == "queued"
    )
    in_progress = sum(
        1
        for item in subtasks
        if isinstance(item, dict) and item.get("status") == "in_progress"
    )
    return {
        "total": len(subtasks),
        "completed": completed,
        "blocked": blocked,
        "queued": queued,
        "in_progress": in_progress,
    }


def _promotion_observation(task: dict) -> dict[str, object]:
    summary = promotion_summary(task)
    return {
        "required": summary.get("required"),
        "status": summary.get("status"),
        "strategy": summary.get("strategy"),
        "pr_number": summary.get("pr_number"),
        "pr_url": summary.get("pr_url"),
        "retarget_required": summary.get("retarget_required"),
        "reverify_required": summary.get("reverify_required"),
    }


def _reason(task: dict, gates: list[dict], conformance: dict) -> str:
    if task.get("status") == "closed":
        return "Task is closed."
    if gates:
        first = gates[0]
        return str(first.get("message") or first.get("code") or "Task has blocking gates.")
    if conformance.get("status") in {"yellow", "red"}:
        return "Conformance drift must be resolved before final closeout."
    if task.get("verify_status") != "passed":
        return "Task has not passed verification."
    return "Task is verified; remaining actions are governed by promotion and closeout gates."


__all__ = ["OBSERVATION_SCHEMA_VERSION", "project_task_observation"]
