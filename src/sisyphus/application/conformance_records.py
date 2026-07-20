from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..domain.task.conformance import (
    CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR,
    CONFORMANCE_CHECKPOINT_POST_EXEC,
    CONFORMANCE_CHECKPOINT_PRE_EXEC,
    CONFORMANCE_CHECKPOINT_SPEC_ANCHOR,
    CONFORMANCE_GREEN,
    CONFORMANCE_RED,
    CONFORMANCE_YELLOW,
    append_conformance_entry,
    ensure_subtask_conformance_defaults,
    ensure_task_conformance_defaults,
    normalize_conformance_status,
)
from ..domain.task.design import ensure_task_design_defaults, summarize_design_anchor
from .ports.clock import ClockPort
from .ports.workflow import TaskRecord


@dataclass(slots=True)
class ConformanceRecordService:
    clock: ClockPort
    new_id: Callable[[], str]

    def mark_spec_anchor(
        self,
        task: TaskRecord,
        *,
        source: str,
        subtask_id: str | None = None,
    ) -> TaskRecord:
        return self.append(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_SPEC_ANCHOR,
            status=CONFORMANCE_GREEN,
            summary="spec re-anchored before execution",
            source=source,
            subtask_id=subtask_id,
            resolved=False,
            drift=0,
        )

    def mark_design_anchor(
        self,
        task: TaskRecord,
        *,
        source: str,
        subtask_id: str | None = None,
    ) -> TaskRecord:
        ensure_task_design_defaults(task)
        design = task["design"]
        return self.append(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR,
            status=CONFORMANCE_GREEN,
            summary=summarize_design_anchor(design.get("frozen", {}) or design),
            source=source,
            subtask_id=subtask_id,
            resolved=False,
            drift=0,
        )

    def pre_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        source: str,
    ) -> tuple[str, str]:
        ensure_task_conformance_defaults(task)
        self.mark_spec_anchor(task, source=source, subtask_id=subtask_id)
        if task.get("design", {}).get("frozen", {}).get("frozen_at"):
            self.mark_design_anchor(task, source=source, subtask_id=subtask_id)
        subtask = _find_subtask(task, subtask_id)
        if subtask is None:
            summary = f"subtask `{subtask_id}` is missing from task metadata"
            self.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
                status=CONFORMANCE_RED,
                summary=summary,
                source=source,
                subtask_id=subtask_id,
                drift=1,
            )
            return CONFORMANCE_RED, summary

        verification_targets = _verification_targets(task)
        if not _subtask_has_verification_mapping(subtask, verification_targets):
            summary = (
                f"subtask `{subtask_id}` has no explicit verification mapping; "
                "execution may continue but verify will block until resolved"
            )
            self.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
                status=CONFORMANCE_YELLOW,
                summary=summary,
                source=source,
                subtask_id=subtask_id,
                drift=0,
            )
            return CONFORMANCE_YELLOW, summary

        summary = f"subtask `{subtask_id}` is anchored to the current spec and verification mapping"
        self.append(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_PRE_EXEC,
            status=CONFORMANCE_GREEN,
            summary=summary,
            source=source,
            subtask_id=subtask_id,
            resolved=True,
            drift=0,
        )
        return CONFORMANCE_GREEN, summary

    def post_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        exit_code: int,
        source: str,
    ) -> tuple[str, str]:
        ensure_task_conformance_defaults(task)
        subtask = _find_subtask(task, subtask_id)
        if subtask is None:
            summary = f"subtask `{subtask_id}` disappeared before post-exec review"
            self.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
                status=CONFORMANCE_RED,
                summary=summary,
                source=source,
                subtask_id=subtask_id,
                drift=1,
            )
            return CONFORMANCE_RED, summary

        if exit_code != 0:
            summary = f"subtask `{subtask_id}` execution failed with exit code `{exit_code}`"
            self.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
                status=CONFORMANCE_RED,
                summary=summary,
                source=source,
                subtask_id=subtask_id,
                drift=1,
            )
            return CONFORMANCE_RED, summary

        verification_targets = _verification_targets(task)
        if not _subtask_has_verification_mapping(subtask, verification_targets):
            summary = (
                f"subtask `{subtask_id}` completed without an explicit verification mapping; "
                "resolve before final verify"
            )
            self.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
                status=CONFORMANCE_YELLOW,
                summary=summary,
                source=source,
                subtask_id=subtask_id,
                drift=0,
            )
            return CONFORMANCE_YELLOW, summary

        summary = f"subtask `{subtask_id}` completed with aligned verification coverage"
        self.append(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_POST_EXEC,
            status=CONFORMANCE_GREEN,
            summary=summary,
            source=source,
            subtask_id=subtask_id,
            resolved=True,
            drift=0,
        )
        return CONFORMANCE_GREEN, summary

    def append(
        self,
        task: TaskRecord,
        *,
        checkpoint_type: str,
        status: str,
        summary: str | None = None,
        source: str | None = None,
        subtask_id: str | None = None,
        resolved: bool = False,
        drift: int = 0,
    ) -> TaskRecord:
        subtask_exists = subtask_id is not None and _find_subtask(task, subtask_id) is not None
        return append_conformance_entry(
            task,
            checkpoint_type=checkpoint_type,
            status=status,
            summary=summary,
            source=source,
            timestamp=self.clock.now(),
            task_event_id=self.new_id(),
            subtask_event_id=self.new_id() if subtask_exists else None,
            resolved=resolved,
            drift=drift,
            subtask_id=subtask_id,
        )


def summarize_task_conformance(task: TaskRecord) -> dict:
    ensure_task_conformance_defaults(task)
    ensure_task_design_defaults(task)
    conformance = task["conformance"]
    design = task["design"]
    subtask_summaries = [
        summarize_subtask_conformance(subtask)
        for subtask in task.get("subtasks", [])
        if isinstance(subtask, dict)
    ]
    return {
        "id": task.get("id"),
        "type": task.get("type"),
        "status": _aggregate_status(
            conformance.get("status"),
            [item["status"] for item in subtask_summaries],
        ),
        "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
        "last_spec_anchor_source": conformance.get("last_spec_anchor_source"),
        "last_design_anchor_at": conformance.get("last_design_anchor_at"),
        "last_design_anchor_source": conformance.get("last_design_anchor_source"),
        "last_checkpoint_type": conformance.get("last_checkpoint_type"),
        "last_checkpoint_source": conformance.get("last_checkpoint_source"),
        "last_checkpoint_at": conformance.get("last_checkpoint_at"),
        "drift_count": int(conformance.get("drift_count", 0)),
        "warning_count": int(conformance.get("warning_count", 0)),
        "unresolved_warning_count": int(conformance.get("unresolved_warning_count", 0)),
        "resolved_warning_count": int(conformance.get("resolved_warning_count", 0)),
        "last_warning": conformance.get("last_warning"),
        "last_failure": conformance.get("last_failure"),
        "design_mode": design.get("mode"),
        "layer_impact": design.get("layer_impact"),
        "design_assessment": dict(design.get("assessment", {})),
        "design_anchor_summary": summarize_design_anchor(design.get("frozen", {}) or design),
        "summary": _compose_summary(conformance, subtask_summaries),
        "subtasks": subtask_summaries,
    }


def summarize_subtask_conformance(subtask: dict) -> dict:
    ensure_subtask_conformance_defaults(subtask)
    conformance = subtask["conformance"]
    return {
        "id": subtask.get("id"),
        "title": subtask.get("title"),
        "category": subtask.get("category"),
        "status": normalize_conformance_status(conformance.get("status")),
        "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
        "last_spec_anchor_source": conformance.get("last_spec_anchor_source"),
        "last_design_anchor_at": conformance.get("last_design_anchor_at"),
        "last_design_anchor_source": conformance.get("last_design_anchor_source"),
        "last_checkpoint_type": conformance.get("last_checkpoint_type"),
        "last_checkpoint_source": conformance.get("last_checkpoint_source"),
        "last_checkpoint_at": conformance.get("last_checkpoint_at"),
        "drift_count": int(conformance.get("drift_count", 0)),
        "warning_count": int(conformance.get("warning_count", 0)),
        "unresolved_warning_count": int(conformance.get("unresolved_warning_count", 0)),
        "resolved_warning_count": int(conformance.get("resolved_warning_count", 0)),
        "last_warning": conformance.get("last_warning"),
        "last_failure": conformance.get("last_failure"),
        "summary": _compose_summary(conformance),
    }


def build_execution_contract(task: TaskRecord, subtask: dict | None = None) -> str:
    task_summary = summarize_task_conformance(task)
    verification_targets = _verification_targets(task)
    lines = [
        f"Task `{task.get('id')}` execution contract",
        "",
        "Conformance model:",
        "- `green` means aligned with the frozen spec.",
        "- `yellow` means a clarification or warning is pending.",
        "- `red` means blocking drift and you must stop.",
        "",
        "Task conformance:",
        f"- status: `{task_summary['status']}`",
        f"- last spec anchor: `{_format_anchor(task_summary['last_spec_anchor_at'], task_summary['last_spec_anchor_source'])}`",
        f"- last design anchor: `{_format_anchor(task_summary['last_design_anchor_at'], task_summary['last_design_anchor_source'])}`",
        f"- last checkpoint: `{_format_checkpoint(task_summary['last_checkpoint_type'], task_summary['last_checkpoint_source'], task_summary['last_checkpoint_at'])}`",
        f"- drift count: `{task_summary['drift_count']}`",
        f"- unresolved warnings: `{task_summary['unresolved_warning_count']}`",
        f"- design mode: `{task_summary['design_mode']}`",
        f"- layer impact: `{task_summary['layer_impact']}`",
    ]
    design_assessment = task_summary.get("design_assessment", {})
    if isinstance(design_assessment, dict) and design_assessment.get("status"):
        lines.append(f"- design assessment: `{design_assessment.get('status')}`")
    if task_summary.get("design_anchor_summary"):
        lines.append(f"- design anchor: `{task_summary['design_anchor_summary']}`")
    if verification_targets:
        lines.append(
            f"- verification targets: `{', '.join(verification_targets[:5])}`"
            f"{' ...' if len(verification_targets) > 5 else ''}"
        )
    if task_summary.get("last_warning"):
        lines.append(f"- last warning: `{_format_summary(task_summary['last_warning'])}`")
    if task_summary.get("last_failure"):
        lines.append(f"- last failure: `{_format_summary(task_summary['last_failure'])}`")

    if subtask is not None:
        subtask_summary = summarize_subtask_conformance(subtask)
        lines.extend(
            [
                "",
                f"Subtask `{subtask_summary['id']}` contract",
                f"- title: `{subtask_summary['title']}`",
                f"- category: `{subtask_summary['category']}`",
                f"- status: `{subtask_summary['status']}`",
                f"- last spec anchor: `{_format_anchor(subtask_summary['last_spec_anchor_at'], subtask_summary['last_spec_anchor_source'])}`",
                f"- last checkpoint: `{_format_checkpoint(subtask_summary['last_checkpoint_type'], subtask_summary['last_checkpoint_source'], subtask_summary['last_checkpoint_at'])}`",
                f"- drift count: `{subtask_summary['drift_count']}`",
                f"- unresolved warnings: `{subtask_summary['unresolved_warning_count']}`",
            ]
        )
        if subtask_summary.get("last_warning"):
            lines.append(f"- last warning: `{_format_summary(subtask_summary['last_warning'])}`")
        if subtask_summary.get("last_failure"):
            lines.append(f"- last failure: `{_format_summary(subtask_summary['last_failure'])}`")

    lines.extend(
        [
            "",
            "Execution rules:",
            "- Re-anchor the implementation to the frozen spec before making changes.",
            "- Keep the work scoped to the requested task or subtask.",
            "- Stop and report if you encounter unresolved warnings or blocking drift.",
            "- Do not broaden scope to unrelated work.",
        ]
    )
    return "\n".join(lines)


def _aggregate_status(task_status: str | None, subtask_statuses: list[str]) -> str:
    statuses = [
        normalize_conformance_status(task_status),
        *[normalize_conformance_status(status) for status in subtask_statuses],
    ]
    if CONFORMANCE_RED in statuses:
        return CONFORMANCE_RED
    if CONFORMANCE_YELLOW in statuses:
        return CONFORMANCE_YELLOW
    return CONFORMANCE_GREEN


def _compose_summary(record: dict, subtask_summaries: list[dict] | None = None) -> str:
    subtask_summaries = subtask_summaries or []
    parts: list[str] = [f"status={record.get('status', CONFORMANCE_GREEN)}"]
    if record.get("last_checkpoint_type"):
        parts.append(f"checkpoint={record['last_checkpoint_type']}")
    if int(record.get("unresolved_warning_count", 0)) > 0:
        parts.append(f"warnings={record['unresolved_warning_count']}")
    if int(record.get("drift_count", 0)) > 0:
        parts.append(f"drift={record['drift_count']}")
    if subtask_summaries:
        parts.append(f"subtasks={len(subtask_summaries)}")
    return ", ".join(parts)


def _format_anchor(at: str | None, source: str | None) -> str:
    if not at and not source:
        return "none"
    if at and source:
        return f"{at} via {source}"
    return str(at or source)


def _format_checkpoint(
    checkpoint_type: str | None,
    source: str | None,
    at: str | None,
) -> str:
    if not checkpoint_type and not source and not at:
        return "none"
    return " / ".join(str(bit) for bit in (checkpoint_type, source, at) if bit)


def _format_summary(event: dict | None) -> str:
    if not event:
        return "none"
    fields = [
        str(event.get("checkpoint_type") or "checkpoint"),
        str(event.get("summary") or "no summary"),
        str(event.get("timestamp") or ""),
    ]
    return " | ".join(field for field in fields if field)


def _find_subtask(task: TaskRecord, subtask_id: str) -> dict | None:
    for subtask in task.get("subtasks", []):
        if isinstance(subtask, dict) and str(subtask.get("id")) == subtask_id:
            return subtask
    return None


def _verification_targets(task: TaskRecord) -> list[str]:
    strategy = task.get("test_strategy", {})
    if not isinstance(strategy, dict):
        return []
    targets = strategy.get("verification_methods", [])
    if not isinstance(targets, list):
        return []
    return [
        target
        for item in targets
        if isinstance(item, dict)
        and (target := str(item.get("target", "")).strip().lower())
    ]


def _subtask_has_verification_mapping(
    subtask: dict,
    verification_targets: list[str],
) -> bool:
    title = str(subtask.get("title", "")).strip().lower()
    return bool(title and title in verification_targets)


__all__ = [
    "ConformanceRecordService",
    "build_execution_contract",
    "summarize_subtask_conformance",
    "summarize_task_conformance",
]
