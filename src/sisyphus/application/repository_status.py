from __future__ import annotations

from .conformance_records import summarize_task_conformance
from ..domain.promotion.state import promotion_summary


def task_status_projection(task: dict) -> dict[str, object]:
    conformance = summarize_task_conformance(task)
    return {
        "task_id": task.get("id"),
        "slug": task.get("slug"),
        "status": task.get("status"),
        "workflow_phase": task.get("workflow_phase"),
        "plan_status": task.get("plan_status"),
        "spec_status": task.get("spec_status"),
        "updated_at": task.get("updated_at"),
        "promotion": promotion_summary(task),
        "conformance": {
            "status": conformance.get("status"),
            "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
            "last_checkpoint_type": conformance.get("last_checkpoint_type"),
            "drift_count": conformance.get("drift_count"),
            "last_warning": conformance.get("last_warning"),
            "last_failure": conformance.get("last_failure"),
            "summary": conformance.get("summary"),
        },
    }


def repository_status_board(
    tasks: list[dict],
    events: list[dict[str, object]],
    metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    rows = [task_status_projection(task) for task in tasks]
    counts = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for row in rows:
        status = str(row.get("conformance", {}).get("status") or "unknown").lower()
        counts[status if status in counts else "unknown"] += 1
    return {
        "summary": {
            "task_count": len(rows),
            "green": counts["green"],
            "yellow": counts["yellow"],
            "red": counts["red"],
            "unknown": counts["unknown"],
        },
        "tasks": rows,
        "recent_events": events,
        "metrics": metrics,
    }


__all__ = ["repository_status_board", "task_status_projection"]
