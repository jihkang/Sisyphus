from __future__ import annotations

from dataclasses import dataclass

from .artifacts import ArtifactRef


@dataclass(frozen=True, slots=True)
class PromotionExecutionResult:
    task_id: str
    branch: str
    base_branch: str
    head_branch: str
    status: str
    commit_sha: str
    pr_number: int | None
    pr_url: str | None
    receipt: ArtifactRef


@dataclass(frozen=True, slots=True)
class MergeReceiptResult:
    task_id: str
    branch: str | None
    pr_number: int
    title: str
    recorded_at: str
    receipt: ArtifactRef
    changeset: ArtifactRef
    close_attempted: bool
    closed: bool
    close_status: str | None
    close_gate_codes: tuple[str, ...]
    child_retargeted_task_ids: tuple[str, ...]


__all__ = ["MergeReceiptResult", "PromotionExecutionResult"]
