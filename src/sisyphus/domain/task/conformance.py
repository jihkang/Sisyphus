from __future__ import annotations


CONFORMANCE_GREEN = "green"
CONFORMANCE_YELLOW = "yellow"
CONFORMANCE_RED = "red"

CONFORMANCE_STATUSES = {
    CONFORMANCE_GREEN,
    CONFORMANCE_YELLOW,
    CONFORMANCE_RED,
}

CONFORMANCE_CHECKPOINT_SPEC_ANCHOR = "spec_anchor"
CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR = "design_anchor"
CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT = "design_assessment"
CONFORMANCE_CHECKPOINT_PRE_EXEC = "pre_exec"
CONFORMANCE_CHECKPOINT_POST_EXEC = "post_exec"
CONFORMANCE_CHECKPOINT_PRE_VERIFY = "pre_verify"


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


def append_conformance_entry(
    task: dict,
    *,
    checkpoint_type: str,
    status: str,
    timestamp: str,
    task_event_id: str,
    summary: str | None = None,
    source: str | None = None,
    subtask_id: str | None = None,
    subtask_event_id: str | None = None,
    resolved: bool = False,
    drift: int = 0,
) -> dict:
    ensure_task_conformance_defaults(task)
    _record_conformance_event(
        task["conformance"],
        event_id=task_event_id,
        checkpoint_type=checkpoint_type,
        status=status,
        summary=summary,
        source=source,
        timestamp=timestamp,
        resolved=resolved,
        drift=drift,
        subtask_id=subtask_id,
    )
    if subtask_id is not None:
        subtask = _find_subtask(task, subtask_id)
        if subtask is not None:
            ensure_subtask_conformance_defaults(subtask)
            _record_conformance_event(
                subtask["conformance"],
                event_id=subtask_event_id or task_event_id,
                checkpoint_type=checkpoint_type,
                status=status,
                summary=summary,
                source=source,
                timestamp=timestamp,
                resolved=resolved,
                drift=drift,
                subtask_id=subtask_id,
            )
    return task


def _record_conformance_event(
    record: dict,
    *,
    event_id: str,
    checkpoint_type: str,
    status: str,
    summary: str | None,
    source: str | None,
    timestamp: str,
    resolved: bool,
    drift: int,
    subtask_id: str | None,
) -> None:
    status = normalize_conformance_status(status)
    entry = {
        "id": event_id,
        "checkpoint_type": checkpoint_type,
        "status": status,
        "summary": summary,
        "source": source,
        "timestamp": timestamp,
        "resolved": resolved,
        "drift": int(drift),
        "subtask_id": subtask_id,
    }
    history = list(record.get("history", []))
    history.append(entry)
    record["history"] = history
    record["last_checkpoint_type"] = checkpoint_type
    record["last_checkpoint_source"] = source
    record["last_checkpoint_at"] = timestamp
    record["summary"] = summary

    if checkpoint_type == CONFORMANCE_CHECKPOINT_SPEC_ANCHOR:
        record["last_spec_anchor_at"] = timestamp
        record["last_spec_anchor_source"] = source
    if checkpoint_type == CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR:
        record["last_design_anchor_at"] = timestamp
        record["last_design_anchor_source"] = source

    if status == CONFORMANCE_RED:
        record["drift_count"] = int(record.get("drift_count", 0)) + max(int(drift), 1)
        record["last_failure"] = _compact_event(entry)
    elif status == CONFORMANCE_YELLOW:
        record["warning_count"] = int(record.get("warning_count", 0)) + 1
        if resolved:
            if int(record.get("unresolved_warning_count", 0)) > 0:
                record["unresolved_warning_count"] = int(record.get("unresolved_warning_count", 0)) - 1
            record["resolved_warning_count"] = int(record.get("resolved_warning_count", 0)) + 1
        else:
            record["unresolved_warning_count"] = int(record.get("unresolved_warning_count", 0)) + 1
        record["last_warning"] = _compact_event(entry)
    elif resolved:
        if int(record.get("unresolved_warning_count", 0)) > 0:
            record["unresolved_warning_count"] = int(record.get("unresolved_warning_count", 0)) - 1
        record["resolved_warning_count"] = int(record.get("resolved_warning_count", 0)) + 1

    record["status"] = _derive_status(record)


def _derive_status(record: dict) -> str:
    if record.get("last_failure") and int(record.get("drift_count", 0)) > 0:
        return CONFORMANCE_RED
    if int(record.get("unresolved_warning_count", 0)) > 0:
        return CONFORMANCE_YELLOW
    return CONFORMANCE_GREEN


def _compact_event(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "checkpoint_type": entry["checkpoint_type"],
        "status": entry["status"],
        "summary": entry["summary"],
        "source": entry["source"],
        "timestamp": entry["timestamp"],
        "resolved": entry["resolved"],
        "subtask_id": entry["subtask_id"],
    }


def _find_subtask(task: dict, subtask_id: str) -> dict | None:
    for subtask in task.get("subtasks", []):
        if isinstance(subtask, dict) and str(subtask.get("id")) == subtask_id:
            return subtask
    return None


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
    "CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR",
    "CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT",
    "CONFORMANCE_CHECKPOINT_POST_EXEC",
    "CONFORMANCE_CHECKPOINT_PRE_EXEC",
    "CONFORMANCE_CHECKPOINT_PRE_VERIFY",
    "CONFORMANCE_CHECKPOINT_SPEC_ANCHOR",
    "CONFORMANCE_GREEN",
    "CONFORMANCE_RED",
    "CONFORMANCE_STATUSES",
    "CONFORMANCE_YELLOW",
    "append_conformance_entry",
    "default_subtask_conformance",
    "default_task_conformance",
    "ensure_subtask_conformance_defaults",
    "ensure_task_conformance_defaults",
    "normalize_conformance_status",
]
