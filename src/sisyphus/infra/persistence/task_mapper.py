from __future__ import annotations

from ...domain.task.models import Task
from .record_mapper import DataclassRecordMapper, FieldMapping


TASK_RECORD_MAPPER = DataclassRecordMapper(
    Task,
    {
        "id": FieldMapping("task_id"),
        "type": FieldMapping("task_type"),
        "slug": FieldMapping("slug"),
        "status": FieldMapping("status"),
        "stage": FieldMapping("stage"),
        "workflow_phase": FieldMapping("workflow_phase"),
        "plan_status": FieldMapping("plan_status"),
        "spec_status": FieldMapping("spec_status"),
        "verify_status": FieldMapping("verify_status"),
    },
)


__all__ = ["TASK_RECORD_MAPPER"]
