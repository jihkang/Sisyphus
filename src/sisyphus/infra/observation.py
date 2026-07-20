from __future__ import annotations

from pathlib import Path


def required_document_status(task: dict, task_dir: Path) -> dict[str, str]:
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


__all__ = ["required_document_status"]
