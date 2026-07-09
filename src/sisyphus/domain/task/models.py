from __future__ import annotations

DEFAULT_CHANGESET_PATH = "CHANGESET.md"
DEFAULT_PROMOTION_RECEIPT_PATH = "artifacts/promotion/merge_receipt.json"


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
