from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CloseOutcome:
    task_id: str
    status: str
    closed: bool
    allow_dirty: bool
    gates: list[dict]


__all__ = ["CloseOutcome"]
