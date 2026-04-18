from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid


CONFORMANCE_GREEN = "green"
CONFORMANCE_YELLOW = "yellow"
CONFORMANCE_RED = "red"

CONFORMANCE_STATUSES = {
    CONFORMANCE_GREEN,
    CONFORMANCE_YELLOW,
    CONFORMANCE_RED,
}

CONFORMANCE_CHECKPOINT_SPEC_ANCHOR = "spec_anchor"
CONFORMANCE_CHECKPOINT_PRE_EXEC = "pre_exec"
CONFORMANCE_CHECKPOINT_POST_EXEC = "post_exec"
CONFORMANCE_CHECKPOINT_PRE_VERIFY = "pre_verify"

CONFORMANCE_WARNING_UNRESOLVED = "CONFORMANCE_WARNING_UNRESOLVED"
CONFORMANCE_BLOCKED = "CONFORMANCE_BLOCKED"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return {
        "policy": "required",
        "status": CONFORMANCE_GREEN,
        "summary": None,
        "last_spec_anchor_at": None,
        "last_spec_anchor_source": None,
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


def ensure_task_conformance_defaults(task: dict) -> dict:
    if not isinstance(task.get("conformance"), dict):
        task["conformance"] = default_task_conformance()
    task_conformance = _ensure_conformance_record(task["conformance"])
    task["conformance"] = task_conformance
    for subtask in task.get("subtasks", []):
        if isinstance(subtask, dict):
            if not isinstance(subtask.get("conformance"), dict):
                subtask["conformance"] = default_subtask_conformance()
            subtask["conformance"] = _ensure_conformance_record(subtask["conformance"])
    return task


def ensure_subtask_conformance_defaults(subtask: dict) -> dict:
    if not isinstance(subtask.get("conformance"), dict):
        subtask["conformance"] = default_subtask_conformance()
    subtask["conformance"] = _ensure_conformance_record(subtask["conformance"])
    return subtask


def summarize_task_conformance(task: dict) -> dict:
    ensure_task_conformance_defaults(task)
    conformance = task["conformance"]
    subtask_summaries = [summarize_subtask_conformance(subtask) for subtask in task.get("subtasks", []) if isinstance(subtask, dict)]
    return {
        "id": task.get("id"),
        "type": task.get("type"),
        "status": _aggregate_status(conformance.get("status"), [item["status"] for item in subtask_summaries]),
        "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
        "last_spec_anchor_source": conformance.get("last_spec_anchor_source"),
        "last_checkpoint_type": conformance.get("last_checkpoint_type"),
        "last_checkpoint_source": conformance.get("last_checkpoint_source"),
        "last_checkpoint_at": conformance.get("last_checkpoint_at"),
        "drift_count": int(conformance.get("drift_count", 0)),
        "warning_count": int(conformance.get("warning_count", 0)),
        "unresolved_warning_count": int(conformance.get("unresolved_warning_count", 0)),
        "resolved_warning_count": int(conformance.get("resolved_warning_count", 0)),
        "last_warning": conformance.get("last_warning"),
        "last_failure": conformance.get("last_failure"),
        "summary": _compose_summary(conformance, subtask_summaries),
        "subtasks": subtask_summaries,
    }


def summarize_subtask_conformance(subtask: dict) -> dict:
    ensure_subtask_conformance_defaults(subtask)
    conformance = subtask["conformance"]
    return {
        "id": subtask.get("id"),
        "title": subtask.get("title"),
        "category": subtask.get("category"),
        "status": normalize_conformance_status(conformance.get("status")),
        "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
        "last_spec_anchor_source": conformance.get("last_spec_anchor_source"),
        "last_checkpoint_type": conformance.get("last_checkpoint_type"),
        "last_checkpoint_source": conformance.get("last_checkpoint_source"),
        "last_checkpoint_at": conformance.get("last_checkpoint_at"),
        "drift_count": int(conformance.get("drift_count", 0)),
        "warning_count": int(conformance.get("warning_count", 0)),
        "unresolved_warning_count": int(conformance.get("unresolved_warning_count", 0)),
        "resolved_warning_count": int(conformance.get("resolved_warning_count", 0)),
        "last_warning": conformance.get("last_warning"),
        "last_failure": conformance.get("last_failure"),
        "summary": _compose_summary(conformance),
    }


def build_execution_contract(task: dict, subtask: dict | None = None) -> str:
    task_summary = summarize_task_conformance(task)
    verification_targets = _verification_targets(task)
    lines = [
        f"Task `{task.get('id')}` execution contract",
        "",
        "Conformance model:",
        "- `green` means aligned with the frozen spec.",
        "- `yellow` means a clarification or warning is pending.",
        "- `red` means blocking drift and you must stop.",
        "",
        "Task conformance:",
        f"- status: `{task_summary['status']}`",
        f"- last spec anchor: `{_format_anchor(task_summary['last_spec_anchor_at'], task_summary['last_spec_anchor_source'])}`",
        f"- last checkpoint: `{_format_checkpoint(task_summary['last_checkpoint_type'], task_summary['last_checkpoint_source'], task_summary['last_checkpoint_at'])}`",
        f"- drift count: `{task_summary['drift_count']}`",
        f"- unresolved warnings: `{task_summary['unresolved_warning_count']}`",
    ]
    if verification_targets:
        lines.append(
            f"- verification targets: `{', '.join(verification_targets[:5])}`"
            f"{' ...' if len(verification_targets) > 5 else ''}"
        )
    if task_summary.get("last_warning"):
        lines.append(f"- last warning: `{_format_summary(task_summary['last_warning'])}`")
    if task_summary.get("last_failure"):
        lines.append(f"- last failure: `{_format_summary(task_summary['last_failure'])}`")

    if subtask is not None:
        subtask_summary = summarize_subtask_conformance(subtask)
        lines.extend(
            [
                "",
                f"Subtask `{subtask_summary['id']}` contract",
                f"- title: `{subtask_summary['title']}`",
                f"- category: `{subtask_summary['category']}`",
                f"- status: `{subtask_summary['status']}`",
                f"- last spec anchor: `{_format_anchor(subtask_summary['last_spec_anchor_at'], subtask_summary['last_spec_anchor_source'])}`",
                f"- last checkpoint: `{_format_checkpoint(subtask_summary['last_checkpoint_type'], subtask_summary['last_checkpoint_source'], subtask_summary['last_checkpoint_at'])}`",
                f"- drift count: `{subtask_summary['drift_count']}`",
                f"- unresolved warnings: `{subtask_summary['unresolved_warning_count']}`",
            ]
        )
        if subtask_summary.get("last_warning"):
            lines.append(f"- last warning: `{_format_summary(subtask_summary['last_warning'])}`")
        if subtask_summary.get("last_failure"):
            lines.append(f"- last failure: `{_format_summary(subtask_summary['last_failure'])}`")

    lines.extend(
        [
            "",
            "Execution rules:",
            "- Re-anchor the implementation to the frozen spec before making changes.",
            "- Keep the work scoped to the requested task or subtask.",
            "- Stop and report if you encounter unresolved warnings or blocking drift.",
            "- Do not broaden scope to unrelated work.",
        ]
    )
    return "\n".join(lines)


def mark_spec_anchor(task: dict, *, source: str, subtask_id: str | None = None) -> dict:
    return append_conformance_log(
        task,
        checkpoint_type=CONFORMANCE_CHECKPOINT_SPEC_ANCHOR,
        status=CONFORMANCE_GREEN,
        summary="spec re-anchored before execution",
        source=source,
        subtask_id=subtask_id,
        resolved=False,
        drift=0,
    )


def run_pre_execution_conformance_check(task: dict, *, subtask_id: str, source: str) -> tuple[str, str]:
    ensure_task_conformance_defaults(task)
    mark_spec_anchor(task, source=source, subtask_id=subtask_id)
    subtask = _find_subtask(task, subtask_id)
    if subtask is None:
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
            status=CONFORMANCE_RED,
            summary=f"subtask `{subtask_id}` is missing from task metadata",
            source=source,
            subtask_id=subtask_id,
            drift=1,
        )
        return CONFORMANCE_RED, f"subtask `{subtask_id}` is missing from task metadata"

    verification_targets = _verification_targets(task)
    if not _subtask_has_verification_mapping(subtask, verification_targets):
        summary = (
            f"subtask `{subtask_id}` has no explicit verification mapping; "
            "execution may continue but verify will block until resolved"
        )
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
            status=CONFORMANCE_YELLOW,
            summary=summary,
            source=source,
            subtask_id=subtask_id,
            drift=0,
        )
        return CONFORMANCE_YELLOW, summary

    summary = f"subtask `{subtask_id}` is anchored to the current spec and verification mapping"
    append_conformance_log(
        task,
        checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
        status=CONFORMANCE_GREEN,
        summary=summary,
        source=source,
        subtask_id=subtask_id,
        resolved=True,
        drift=0,
    )
    return CONFORMANCE_GREEN, summary


def run_post_execution_conformance_check(
    task: dict,
    *,
    subtask_id: str,
    exit_code: int,
    source: str,
) -> tuple[str, str]:
    ensure_task_conformance_defaults(task)
    subtask = _find_subtask(task, subtask_id)
    if subtask is None:
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
            status=CONFORMANCE_RED,
            summary=f"subtask `{subtask_id}` disappeared before post-exec review",
            source=source,
            subtask_id=subtask_id,
            drift=1,
        )
        return CONFORMANCE_RED, f"subtask `{subtask_id}` disappeared before post-exec review"

    if exit_code != 0:
        summary = f"subtask `{subtask_id}` execution failed with exit code `{exit_code}`"
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
            status=CONFORMANCE_RED,
            summary=summary,
            source=source,
            subtask_id=subtask_id,
            drift=1,
        )
        return CONFORMANCE_RED, summary

    verification_targets = _verification_targets(task)
    if not _subtask_has_verification_mapping(subtask, verification_targets):
        summary = (
            f"subtask `{subtask_id}` completed without an explicit verification mapping; "
            "resolve before final verify"
        )
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
            status=CONFORMANCE_YELLOW,
            summary=summary,
            source=source,
            subtask_id=subtask_id,
            drift=0,
        )
        return CONFORMANCE_YELLOW, summary

    summary = f"subtask `{subtask_id}` completed with aligned verification coverage"
    append_conformance_log(
        task,
        checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
        status=CONFORMANCE_GREEN,
        summary=summary,
        source=source,
        subtask_id=subtask_id,
        resolved=True,
        drift=0,
    )
    return CONFORMANCE_GREEN, summary


def append_conformance_log_markdown(task: dict, task_dir: Path, *, limit: int = 20) -> None:
    docs = task.get("docs", {})
    if not isinstance(docs, dict):
        return
    log_name = docs.get("log")
    if not log_name:
        return
    log_path = task_dir / str(log_name)
    if not log_path.exists():
        return

    ensure_task_conformance_defaults(task)
    history = list(task.get("conformance", {}).get("history", []))
    if not history:
        return

    lines = [
        "## Conformance Checks",
        "",
    ]
    for entry in history[-limit:]:
        timestamp = entry.get("timestamp") or "unknown-time"
        checkpoint_type = entry.get("checkpoint_type") or "checkpoint"
        status = entry.get("status") or CONFORMANCE_GREEN
        summary = entry.get("summary") or "no summary"
        subtask_suffix = f" subtask={entry.get('subtask_id')}" if entry.get("subtask_id") else ""
        lines.append(f"- {timestamp} `{checkpoint_type}` `{status}`{subtask_suffix}: {summary}")

    original = log_path.read_text(encoding="utf-8")
    marker = "## Conformance Checks"
    if marker in original:
        original = original.split(marker, 1)[0].rstrip()
    rendered = original.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    log_path.write_text(rendered, encoding="utf-8")


def append_conformance_log(
    task: dict,
    *,
    checkpoint_type: str,
    status: str,
    summary: str | None = None,
    source: str | None = None,
    subtask_id: str | None = None,
    resolved: bool = False,
    drift: int = 0,
) -> dict:
    ensure_task_conformance_defaults(task)
    timestamp = utc_now()
    _record_conformance_event(
        task["conformance"],
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


def collect_conformance_gates(task: dict, *, action: str) -> list[dict]:
    summary = summarize_task_conformance(task)
    gates: list[dict] = []
    if summary["status"] == CONFORMANCE_RED:
        gates.append(
            _gate(
                CONFORMANCE_BLOCKED,
                f"task conformance has blocking drift before {action}",
                source="conformance",
                severity=CONFORMANCE_RED,
                checkpoint_type=summary.get("last_checkpoint_type"),
            )
        )
    if summary["unresolved_warning_count"] > 0:
        gates.append(
            _gate(
                CONFORMANCE_WARNING_UNRESOLVED,
                f"task conformance has unresolved warnings before {action}",
                source="conformance",
                severity=CONFORMANCE_YELLOW,
                checkpoint_type=summary.get("last_checkpoint_type"),
            )
        )

    for subtask in summary["subtasks"]:
        if subtask["status"] == CONFORMANCE_RED:
            gates.append(
                _gate(
                    CONFORMANCE_BLOCKED,
                    f"subtask `{subtask.get('id')}` has blocking drift before {action}",
                    source="conformance",
                    severity=CONFORMANCE_RED,
                    checkpoint_type=subtask.get("last_checkpoint_type"),
                    subtask_id=subtask.get("id"),
                )
            )
        if subtask["unresolved_warning_count"] > 0:
            gates.append(
                _gate(
                    CONFORMANCE_WARNING_UNRESOLVED,
                    f"subtask `{subtask.get('id')}` has unresolved warnings before {action}",
                    source="conformance",
                    severity=CONFORMANCE_YELLOW,
                    checkpoint_type=subtask.get("last_checkpoint_type"),
                    subtask_id=subtask.get("id"),
                )
            )
    return _dedupe_gates(gates)


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


def _record_conformance_event(
    record: dict,
    *,
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
        "id": uuid.uuid4().hex,
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


def _aggregate_status(task_status: str | None, subtask_statuses: list[str]) -> str:
    statuses = [normalize_conformance_status(task_status), *[normalize_conformance_status(status) for status in subtask_statuses]]
    if CONFORMANCE_RED in statuses:
        return CONFORMANCE_RED
    if CONFORMANCE_YELLOW in statuses:
        return CONFORMANCE_YELLOW
    return CONFORMANCE_GREEN


def _compose_summary(record: dict, subtask_summaries: list[dict] | None = None) -> str:
    subtask_summaries = subtask_summaries or []
    parts: list[str] = [f"status={record.get('status', CONFORMANCE_GREEN)}"]
    if record.get("last_checkpoint_type"):
        parts.append(f"checkpoint={record['last_checkpoint_type']}")
    if int(record.get("unresolved_warning_count", 0)) > 0:
        parts.append(f"warnings={record['unresolved_warning_count']}")
    if int(record.get("drift_count", 0)) > 0:
        parts.append(f"drift={record['drift_count']}")
    if subtask_summaries:
        parts.append(f"subtasks={len(subtask_summaries)}")
    return ", ".join(parts)


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


def _format_anchor(at: str | None, source: str | None) -> str:
    if not at and not source:
        return "none"
    if at and source:
        return f"{at} via {source}"
    return str(at or source)


def _format_checkpoint(checkpoint_type: str | None, source: str | None, at: str | None) -> str:
    if not checkpoint_type and not source and not at:
        return "none"
    bits = [bit for bit in [checkpoint_type, source, at] if bit]
    return " / ".join(str(bit) for bit in bits)


def _format_summary(event: dict | None) -> str:
    if not event:
        return "none"
    fields = [
        str(event.get("checkpoint_type") or "checkpoint"),
        str(event.get("summary") or "no summary"),
        str(event.get("timestamp") or ""),
    ]
    return " | ".join(field for field in fields if field)


def _find_subtask(task: dict, subtask_id: str) -> dict | None:
    for subtask in task.get("subtasks", []):
        if isinstance(subtask, dict) and str(subtask.get("id")) == subtask_id:
            return subtask
    return None


def _verification_targets(task: dict) -> list[str]:
    strategy = task.get("test_strategy", {})
    if not isinstance(strategy, dict):
        return []
    targets = strategy.get("verification_methods", [])
    if not isinstance(targets, list):
        return []
    values: list[str] = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip()
        if target:
            values.append(target.lower())
    return values


def _subtask_has_verification_mapping(subtask: dict, verification_targets: list[str]) -> bool:
    title = str(subtask.get("title", "")).strip().lower()
    if not title:
        return False
    return title in verification_targets


def _gate(
    code: str,
    message: str,
    *,
    source: str,
    severity: str,
    checkpoint_type: str | None = None,
    subtask_id: str | None = None,
) -> dict:
    gate = {
        "code": code,
        "message": message,
        "blocking": True,
        "source": source,
        "created_at": utc_now(),
        "severity": severity,
    }
    if checkpoint_type:
        gate["checkpoint_type"] = checkpoint_type
    if subtask_id:
        gate["subtask_id"] = subtask_id
    return gate


def _dedupe_gates(gates: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    deduped: list[dict] = []
    for gate in gates:
        key = (
            gate.get("code", ""),
            gate.get("message", ""),
            gate.get("checkpoint_type"),
            gate.get("subtask_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gate)
    return deduped
