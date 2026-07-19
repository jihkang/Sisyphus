from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdoptedChanges:
    source_branch: str | None
    source_repo_root: str
    paths: tuple[str, ...]
    deleted_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromotionMergeReceipt:
    task_id: str
    branch: str | None
    pr_number: int
    title: str
    recorded_at: str
    receipt_path: str
    changeset_path: str
    close_attempted: bool
    closed: bool
    close_status: str | None
    close_gate_codes: tuple[str, ...]
    child_retargeted_task_ids: tuple[str, ...]


__all__ = ["AdoptedChanges", "PromotionMergeReceipt"]
