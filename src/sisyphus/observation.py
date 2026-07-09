from __future__ import annotations

from pathlib import Path

from .action_space import allowed_policy_actions, forbidden_policy_actions
from .config import SisyphusConfig
from .conformance import summarize_task_conformance
from .evidence_graph import summarize_evidence_graph
from .fingerprint import stable_json_hash
from .promotion_state import promotion_summary
from .state import load_task_record


OBSERVATION_SCHEMA_VERSION = "sisyphus.task_observation.v1"


def render_task_observation(repo_root: Path, config: SisyphusConfig, task_id: str) -> dict[str, object]:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    return build_task_observation(task, task_file.parent)


def build_task_observation(task: dict, task_dir: Path) -> dict[str, object]:
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
        "required_docs": _required_doc_status(task, task_dir),
        "subtasks": _subtask_summary(task),
        "evidence_summary": summarize_evidence_graph(task, task_dir),
        "promotion": _promotion_observation(task),
        "allowed_next_actions": list(allowed_policy_actions(task)),
        "forbidden_next_actions": list(forbidden_policy_actions(task)),
        "reason": _reason(task, gates, conformance),
    }
    observation["observation_hash"] = stable_json_hash(observation)
    return observation


def _required_doc_status(task: dict, task_dir: Path) -> dict[str, str]:
    docs = task.get("docs", {})
    if not isinstance(docs, dict):
        return {}
    statuses: dict[str, str] = {}
    for key in _required_doc_keys(task):
        relative_path = docs.get(key)
        if not relative_path:
            statuses[key] = "missing"
            continue
        statuses[key] = "present" if (task_dir / str(relative_path)).exists() else "missing"
    return statuses


def _required_doc_keys(task: dict) -> tuple[str, ...]:
    if task.get("type") == "issue":
        return ("brief", "repro", "fix_plan", "verify", "log")
    return ("brief", "plan", "verify", "log", "changeset")


def _subtask_summary(task: dict) -> dict[str, int]:
    subtasks = task.get("subtasks", [])
    if not isinstance(subtasks, list):
        subtasks = []
    completed = sum(1 for item in subtasks if isinstance(item, dict) and item.get("status") == "completed")
    blocked = sum(1 for item in subtasks if isinstance(item, dict) and item.get("status") in {"blocked", "failed"})
    queued = sum(1 for item in subtasks if isinstance(item, dict) and item.get("status") == "queued")
    in_progress = sum(1 for item in subtasks if isinstance(item, dict) and item.get("status") == "in_progress")
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


__all__ = ["OBSERVATION_SCHEMA_VERSION", "build_task_observation", "render_task_observation"]
