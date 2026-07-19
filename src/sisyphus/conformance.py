from __future__ import annotations

from datetime import datetime, timezone
import uuid

from .application.conformance_records import (
    ConformanceRecordService,
    build_execution_contract,
    summarize_subtask_conformance,
    summarize_task_conformance,
)
from .application.planning_records import dedupe_gate_records, make_gate_record
from .domain.task.conformance import (
    CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR,
    CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
    CONFORMANCE_CHECKPOINT_POST_EXEC,
    CONFORMANCE_CHECKPOINT_PRE_EXEC,
    CONFORMANCE_CHECKPOINT_PRE_VERIFY,
    CONFORMANCE_CHECKPOINT_SPEC_ANCHOR,
    CONFORMANCE_GREEN,
    CONFORMANCE_RED,
    CONFORMANCE_STATUSES,
    CONFORMANCE_YELLOW,
    append_conformance_entry,
    default_subtask_conformance,
    default_task_conformance,
    ensure_subtask_conformance_defaults,
    ensure_task_conformance_defaults,
    normalize_conformance_status,
)
from .infra.documents.conformance_log import append_conformance_log_markdown


CONFORMANCE_WARNING_UNRESOLVED = "CONFORMANCE_WARNING_UNRESOLVED"
CONFORMANCE_BLOCKED = "CONFORMANCE_BLOCKED"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class _FacadeClock:
    def now(self) -> str:
        return utc_now()


def _records() -> ConformanceRecordService:
    return ConformanceRecordService(clock=_FacadeClock(), new_id=lambda: uuid.uuid4().hex)


def mark_spec_anchor(task: dict, *, source: str, subtask_id: str | None = None) -> dict:
    return _records().mark_spec_anchor(task, source=source, subtask_id=subtask_id)


def mark_design_anchor(task: dict, *, source: str, subtask_id: str | None = None) -> dict:
    return _records().mark_design_anchor(task, source=source, subtask_id=subtask_id)


def run_pre_execution_conformance_check(
    task: dict,
    *,
    subtask_id: str,
    source: str,
) -> tuple[str, str]:
    return _records().pre_execution(task, subtask_id=subtask_id, source=source)


def run_post_execution_conformance_check(
    task: dict,
    *,
    subtask_id: str,
    exit_code: int,
    source: str,
) -> tuple[str, str]:
    return _records().post_execution(
        task,
        subtask_id=subtask_id,
        exit_code=exit_code,
        source=source,
    )


def append_conformance_log(
    task: dict,
    *,
    checkpoint_type: str,
    status: str,
    summary: str | None = None,
    source: str | None = None,
    subtask_id: str | None = None,
    resolved: bool = False,
    drift: int = 0,
) -> dict:
    return _records().append(
        task,
        checkpoint_type=checkpoint_type,
        status=status,
        summary=summary,
        source=source,
        subtask_id=subtask_id,
        resolved=resolved,
        drift=drift,
    )


def collect_conformance_gates(task: dict, *, action: str) -> list[dict]:
    summary = summarize_task_conformance(task)
    gates: list[dict] = []
    if summary["status"] == CONFORMANCE_RED:
        gates.append(
            make_gate_record(
                CONFORMANCE_BLOCKED,
                f"task conformance has blocking drift before {action}",
                "conformance",
                created_at=utc_now(),
                severity=CONFORMANCE_RED,
                checkpoint_type=summary.get("last_checkpoint_type"),
            )
        )
    if summary["unresolved_warning_count"] > 0:
        gates.append(
            make_gate_record(
                CONFORMANCE_WARNING_UNRESOLVED,
                f"task conformance has unresolved warnings before {action}",
                "conformance",
                created_at=utc_now(),
                severity=CONFORMANCE_YELLOW,
                checkpoint_type=summary.get("last_checkpoint_type"),
            )
        )

    for subtask in summary["subtasks"]:
        if subtask["status"] == CONFORMANCE_RED:
            gates.append(
                make_gate_record(
                    CONFORMANCE_BLOCKED,
                    f"subtask `{subtask.get('id')}` has blocking drift before {action}",
                    "conformance",
                    created_at=utc_now(),
                    severity=CONFORMANCE_RED,
                    checkpoint_type=subtask.get("last_checkpoint_type"),
                    subtask_id=subtask.get("id"),
                )
            )
        if subtask["unresolved_warning_count"] > 0:
            gates.append(
                make_gate_record(
                    CONFORMANCE_WARNING_UNRESOLVED,
                    f"subtask `{subtask.get('id')}` has unresolved warnings before {action}",
                    "conformance",
                    created_at=utc_now(),
                    severity=CONFORMANCE_YELLOW,
                    checkpoint_type=subtask.get("last_checkpoint_type"),
                    subtask_id=subtask.get("id"),
                )
            )
    return dedupe_gate_records(gates)


__all__ = [
    "CONFORMANCE_BLOCKED",
    "CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR",
    "CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT",
    "CONFORMANCE_CHECKPOINT_POST_EXEC",
    "CONFORMANCE_CHECKPOINT_PRE_EXEC",
    "CONFORMANCE_CHECKPOINT_PRE_VERIFY",
    "CONFORMANCE_CHECKPOINT_SPEC_ANCHOR",
    "CONFORMANCE_GREEN",
    "CONFORMANCE_RED",
    "CONFORMANCE_STATUSES",
    "CONFORMANCE_WARNING_UNRESOLVED",
    "CONFORMANCE_YELLOW",
    "append_conformance_entry",
    "append_conformance_log",
    "append_conformance_log_markdown",
    "build_execution_contract",
    "collect_conformance_gates",
    "default_subtask_conformance",
    "default_task_conformance",
    "ensure_subtask_conformance_defaults",
    "ensure_task_conformance_defaults",
    "mark_design_anchor",
    "mark_spec_anchor",
    "normalize_conformance_status",
    "run_post_execution_conformance_check",
    "run_pre_execution_conformance_check",
    "summarize_subtask_conformance",
    "summarize_task_conformance",
    "utc_now",
]
