from __future__ import annotations


CONFORMANCE_GREEN = "green"
CONFORMANCE_YELLOW = "yellow"
CONFORMANCE_RED = "red"

CONFORMANCE_STATUSES = {
    CONFORMANCE_GREEN,
    CONFORMANCE_YELLOW,
    CONFORMANCE_RED,
}


def normalize_conformance_status(value: str | None) -> str:
    status = str(value or CONFORMANCE_GREEN).strip().lower()
    if status not in CONFORMANCE_STATUSES:
        return CONFORMANCE_GREEN
    return status


def default_task_conformance() -> dict:
    return {
        "policy": "required",
        "status": CONFORMANCE_GREEN,
        "summary": None,
        "last_spec_anchor_at": None,
        "last_spec_anchor_source": None,
        "last_design_anchor_at": None,
        "last_design_anchor_source": None,
        "last_checkpoint_type": None,
        "last_checkpoint_source": None,
        "last_checkpoint_at": None,
        "drift_count": 0,
        "warning_count": 0,
        "unresolved_warning_count": 0,
        "resolved_warning_count": 0,
        "last_warning": None,
        "last_failure": None,
        "history": [],
    }


def default_subtask_conformance() -> dict:
    return default_task_conformance()


def ensure_task_conformance_defaults(task: dict) -> dict:
    if not isinstance(task.get("conformance"), dict):
        task["conformance"] = default_task_conformance()
    task["conformance"] = _ensure_conformance_record(task["conformance"])
    for subtask in task.get("subtasks", []):
        if isinstance(subtask, dict):
            ensure_subtask_conformance_defaults(subtask)
    return task


def ensure_subtask_conformance_defaults(subtask: dict) -> dict:
    if not isinstance(subtask.get("conformance"), dict):
        subtask["conformance"] = default_subtask_conformance()
    subtask["conformance"] = _ensure_conformance_record(subtask["conformance"])
    return subtask


def _ensure_conformance_record(record: dict) -> dict:
    defaults = default_task_conformance()
    for key, value in defaults.items():
        if key not in record:
            record[key] = value if not isinstance(value, list) else []
    record["status"] = normalize_conformance_status(record.get("status"))
    record["drift_count"] = int(record.get("drift_count", 0))
    record["warning_count"] = int(record.get("warning_count", 0))
    record["unresolved_warning_count"] = int(record.get("unresolved_warning_count", 0))
    record["resolved_warning_count"] = int(record.get("resolved_warning_count", 0))
    record["history"] = list(record.get("history", []))
    return record


__all__ = [
    "CONFORMANCE_GREEN",
    "CONFORMANCE_RED",
    "CONFORMANCE_STATUSES",
    "CONFORMANCE_YELLOW",
    "default_subtask_conformance",
    "default_task_conformance",
    "ensure_subtask_conformance_defaults",
    "ensure_task_conformance_defaults",
    "normalize_conformance_status",
]
