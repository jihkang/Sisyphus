from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromotionBaseResolution:
    base_branch: str
    source: str
    reason: str
    parent_task_id: str | None
    parent_artifact_id: str | None
    parent_branch: str | None


__all__ = ["PromotionBaseResolution"]
