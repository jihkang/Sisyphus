from __future__ import annotations

from pathlib import Path
import json

from ...artifact_resources import is_feature_task_artifact_resource, read_feature_task_artifact_resource
from ...config import SisyphusConfig
from ...conformance import ensure_task_conformance_defaults, summarize_subtask_conformance, summarize_task_conformance
from ...evidence_graph import evidence_resource_payload
from ...observation import build_task_observation
from ...promotion_state import promotion_summary
from ...state import load_task_record
from ...spec_validation import spec_validation_resource_payload
from ..agent_queries import list_agents


def read_task_resource(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    parsed,
    load_record=load_task_record,
    list_agents_fn=list_agents,
    is_artifact_resource=is_feature_task_artifact_resource,
    read_artifact_resource=read_feature_task_artifact_resource,
    observation_payload=build_task_observation,
    evidence_payload=evidence_resource_payload,
) -> dict[str, object] | str:
    task_id = parsed.netloc
    resource_name = parsed.path.lstrip("/")
    task, task_file = load_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent

    if resource_name == "record":
        return {"task": task}
    if resource_name == "observation":
        return observation_payload(task, task_dir)
    if resource_name == "conformance":
        return {"conformance": summarize_task_conformance(task)}
    if resource_name == "evidence":
        return evidence_payload(task, task_dir)
    if resource_name == "timeline":
        return _task_timeline_resource(task)
    if resource_name == "spec-validation":
        return spec_validation_resource_payload(task, task_dir)
    if resource_name == "promotion":
        doc_path = task_dir / str(task["docs"].get("promotion"))
        if not doc_path.exists():
            return _promotion_resource_placeholder(task)
        return json.loads(doc_path.read_text(encoding="utf-8"))
    if resource_name == "changeset":
        doc_path = task_dir / str(task["docs"].get("changeset"))
        if not doc_path.exists():
            return _changeset_resource_placeholder(task)
        return doc_path.read_text(encoding="utf-8")
    if resource_name == "agents":
        return {
            "agents": list_agents_fn(
                repo_root=repo_root,
                config=config,
                task_id=task_id,
            )
        }
    if is_artifact_resource(resource_name):
        if task.get("type") != "feature":
            return _artifact_resource_unavailable(
                task,
                resource_name=resource_name,
                reason="resource is only available for feature tasks",
            )
        try:
            return read_artifact_resource(task, task_dir, resource_name)
        except Exception as exc:
            return _artifact_resource_unavailable(
                task,
                resource_name=resource_name,
                reason=str(exc) or "artifact projection is not available for the current task state",
            )

    doc_key = _resource_doc_key(resource_name, task)
    if doc_key is None:
        raise ValueError(f"unsupported task resource `{resource_name}` for task://{task_id}")

    doc_name = task["docs"].get(doc_key)
    if not doc_name:
        raise FileNotFoundError(f"task `{task_id}` does not define document `{doc_key}`")
    doc_path = task_dir / str(doc_name)
    if not doc_path.exists():
        raise FileNotFoundError(f"task document not found: {doc_path}")
    return doc_path.read_text(encoding="utf-8")


def _resource_doc_key(resource_name: str, task: dict) -> str | None:
    if resource_name == "brief":
        return "brief"
    if resource_name == "plan":
        if task.get("type") == "feature":
            return "plan"
        return "fix_plan"
    if resource_name == "verify":
        return "verify"
    if resource_name == "log":
        return "log"
    if resource_name == "repro" and task.get("type") == "issue":
        return "repro"
    return None


def _promotion_resource_placeholder(task: dict) -> dict[str, object]:
    return {
        "task_id": task.get("id"),
        "status": "not_recorded",
        "promotion": promotion_summary(task),
    }


def _changeset_resource_placeholder(task: dict) -> str:
    return "\n".join(
        [
            "# Changeset",
            "",
            f"- Task: `{task.get('id')}`",
            "- Status: `not_recorded`",
            "- Notes: no merged pull request receipt has been recorded for this task yet",
            "",
        ]
    )


def _artifact_resource_unavailable(task: dict, *, resource_name: str, reason: str) -> dict[str, object]:
    return {
        "task_id": task.get("id"),
        "task_type": task.get("type"),
        "resource": resource_name,
        "status": "unavailable",
        "reason": reason,
    }


def _task_timeline_resource(task: dict) -> dict[str, object]:
    ensure_task_conformance_defaults(task)
    task_summary = summarize_task_conformance(task)
    task_history = list(task.get("conformance", {}).get("history", []))
    subtasks = task.get("subtasks", [])
    subtask_timelines: list[dict[str, object]] = []
    if isinstance(subtasks, list):
        for subtask in subtasks:
            if not isinstance(subtask, dict):
                continue
            subtask_timelines.append(
                {
                    "subtask_id": subtask.get("id"),
                    "title": subtask.get("title"),
                    "status": summarize_subtask_conformance(subtask).get("status"),
                    "history": list(subtask.get("conformance", {}).get("history", [])),
                }
            )
    return {
        "task_id": task.get("id"),
        "summary": {
            "status": task_summary.get("status"),
            "drift_count": task_summary.get("drift_count"),
            "warning_count": task_summary.get("warning_count"),
            "unresolved_warning_count": task_summary.get("unresolved_warning_count"),
            "last_checkpoint_type": task_summary.get("last_checkpoint_type"),
            "last_checkpoint_at": task_summary.get("last_checkpoint_at"),
            "last_warning": task_summary.get("last_warning"),
            "last_failure": task_summary.get("last_failure"),
        },
        "task_history": task_history,
        "subtasks": subtask_timelines,
    }


__all__ = ["read_task_resource"]
