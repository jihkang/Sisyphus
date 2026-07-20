from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RepositoryPromotionExecutionResult:
    task_id: str | None
    status: str | None
    branch: str | None
    base_branch: str | None
    head_branch: str | None
    commit_sha: str | None
    pr_number: int | None
    pr_url: str | None
    receipt_path: Path | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None and self.task_id is not None


__all__ = ["RepositoryPromotionExecutionResult"]
