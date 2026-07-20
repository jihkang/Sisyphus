from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlanStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class SpecStatus(str, Enum):
    DRAFT = "draft"
    FROZEN = "frozen"


@dataclass(frozen=True, slots=True)
class PlanReviewState:
    status: PlanStatus
    review_round: int = 0
    max_review_rounds: int = 3


@dataclass(frozen=True, slots=True)
class SpecState:
    status: SpecStatus


def normalize_plan_status(value: object, *, default: PlanStatus = PlanStatus.APPROVED) -> PlanStatus:
    try:
        return PlanStatus(str(value or default.value))
    except ValueError:
        return default


def normalize_spec_status(value: object, *, default: SpecStatus = SpecStatus.FROZEN) -> SpecStatus:
    try:
        return SpecStatus(str(value or default.value))
    except ValueError:
        return default


__all__ = [
    "PlanReviewState",
    "PlanStatus",
    "SpecState",
    "SpecStatus",
    "normalize_plan_status",
    "normalize_spec_status",
]
