from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateTaskRecordCommand:
    task_type: str
    slug: str
    spec_validation_required: bool = False


__all__ = ["CreateTaskRecordCommand"]
