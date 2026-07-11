from __future__ import annotations


def normalize_terminal_lifecycle_state(task: dict) -> None:
    status = str(task.get("status") or "").strip().lower()
    closed_at = str(task.get("closed_at") or "").strip()
    if status != "closed" and not closed_at:
        return
    task["status"] = "closed"
    task["stage"] = "done"
    task["workflow_phase"] = "closed"


__all__ = [
    "normalize_terminal_lifecycle_state",
]
