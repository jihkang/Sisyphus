from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerificationStatus(str, Enum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CommandExecution:
    name: str
    command: str
    status: VerificationStatus
    exit_code: int
    started_at: str
    finished_at: str
    duration_ms: int | None
    output_excerpt: str


__all__ = ["CommandExecution", "VerificationStatus"]
