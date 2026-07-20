from __future__ import annotations

from pathlib import Path

from ...domain.task.conformance import CONFORMANCE_GREEN, ensure_task_conformance_defaults


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

    lines = ["## Conformance Checks", ""]
    for entry in history[-limit:]:
        timestamp = entry.get("timestamp") or "unknown-time"
        checkpoint_type = entry.get("checkpoint_type") or "checkpoint"
        status = entry.get("status") or CONFORMANCE_GREEN
        summary = entry.get("summary") or "no summary"
        subtask_suffix = (
            f" subtask={entry.get('subtask_id')}" if entry.get("subtask_id") else ""
        )
        lines.append(
            f"- {timestamp} `{checkpoint_type}` `{status}`{subtask_suffix}: {summary}"
        )

    original = log_path.read_text(encoding="utf-8")
    marker = "## Conformance Checks"
    if marker in original:
        original = original.split(marker, 1)[0].rstrip()
    rendered = original.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    log_path.write_text(rendered, encoding="utf-8")


__all__ = ["append_conformance_log_markdown"]
