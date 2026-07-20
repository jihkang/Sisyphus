from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CHANGESET_PATH = "CHANGESET.md"
DEFAULT_PROMOTION_RECEIPT_PATH = "artifacts/promotion/merge_receipt.json"


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str | None = None
    task_type: str | None = None
    slug: str | None = None
    status: str = "open"
    stage: str = "spec"
    workflow_phase: str = "plan_in_review"
    plan_status: str = "pending_review"
    spec_status: str = "draft"
    verify_status: str = "not_run"


def default_task_docs(task_type: str | None) -> dict[str, str]:
    docs = {
        "brief": "BRIEF.md",
        "verify": "VERIFY.md",
        "log": "LOG.md",
        "changeset": DEFAULT_CHANGESET_PATH,
        "promotion": DEFAULT_PROMOTION_RECEIPT_PATH,
    }
    if task_type == "issue":
        docs["repro"] = "REPRO.md"
        docs["fix_plan"] = "FIX_PLAN.md"
        return docs
    docs["plan"] = "PLAN.md"
    return docs


__all__ = [
    "DEFAULT_CHANGESET_PATH",
    "DEFAULT_PROMOTION_RECEIPT_PATH",
    "Task",
    "default_task_docs",
]
