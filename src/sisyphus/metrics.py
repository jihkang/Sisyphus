from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
import json

from .bus_jsonl import resolve_event_bus_path
from .config import SisyphusConfig
from .events import new_event_envelope
from .paths import event_log_file
from .state import list_task_records, utc_now


MANUAL_INTERVENTION_REQUIRED_EVENT = "task.manual_intervention_required"
REOPENED_AFTER_VERIFY_EVENT = "task.reopened_after_verify"
MANUAL_INTERVENTION_PHASES = frozenset(
    {
        "plan_in_review",
        "plan_revision",
        "needs_user_input",
        "spec_drafting",
        "spec_in_review",
        "promotion_pending",
        "retarget_required",
    }
)


def publish_manual_intervention_required(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str,
    reason: str,
    workflow_phase: str | None = None,
    status: str | None = None,
    detail: str | None = None,
) -> None:
    data: dict[str, object] = {
        "task_id": task_id,
        "reason": reason,
    }
    if workflow_phase:
        data["workflow_phase"] = workflow_phase
    if status:
        data["status"] = status
    if detail:
        data["detail"] = detail
    _emit_metric_event(
        repo_root,
        config,
        new_event_envelope(
            MANUAL_INTERVENTION_REQUIRED_EVENT,
            source={"module": "metrics"},
            data=data,
        ),
    )


def publish_reopened_after_verify(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str,
    reason: str,
    workflow_phase: str | None = None,
    previous_verify_status: str | None = None,
) -> None:
    data: dict[str, object] = {
        "task_id": task_id,
        "reason": reason,
    }
    if workflow_phase:
        data["workflow_phase"] = workflow_phase
    if previous_verify_status:
        data["previous_verify_status"] = previous_verify_status
    _emit_metric_event(
        repo_root,
        config,
        new_event_envelope(
            REOPENED_AFTER_VERIFY_EVENT,
            source={"module": "metrics"},
            data=data,
        ),
    )


def build_value_metrics_report(repo_root: Path, config: SisyphusConfig) -> dict[str, object]:
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
    paths = _metrics_event_paths(repo_root, config)
    entries = _read_metric_entries(paths)
    session_resume_samples = _session_resume_samples(entries)
    promotion_samples = _promotion_lead_time_samples(tasks)
    verified_task_ids = _verified_task_ids(tasks, entries)
    reopened_task_ids = _reopened_after_verify_task_ids(tasks, entries)
    manual_events = _manual_intervention_events(entries)
    manual_reason_counts = Counter(str(event.get("data", {}).get("reason") or "unknown") for event in manual_events)
    pending_manual_tasks = [
        {
            "task_id": str(task.get("id")),
            "workflow_phase": str(task.get("workflow_phase") or ""),
            "status": str(task.get("status") or ""),
        }
        for task in tasks
        if str(task.get("workflow_phase") or "") in MANUAL_INTERVENTION_PHASES
    ]
    reopen_denominator = len(verified_task_ids)
    reopen_numerator = len(reopened_task_ids & verified_task_ids) if verified_task_ids else len(reopened_task_ids)

    return {
        "generated_at": utc_now(),
        "sources": {
            "task_count": len(tasks),
            "event_log_paths": [str(path) for path in paths],
            "event_entry_count": len(entries),
        },
        "definitions": {
            "session_resume_time": "Seconds from a queued inbox event to the same event being processed. This measures how quickly persisted work can be resumed into task state.",
            "reopen_rate_after_verify": "Share of verified tasks that later emitted a reopen-after-verify signal and now require another operator or execution pass.",
            "promotion_lead_time": "Seconds from a task's successful verify timestamp to promotion being recorded from a merged pull request.",
            "manual_intervention_count": "Count of explicit task.manual_intervention_required events emitted when the workflow needs plan review, spec freeze, promotion, retarget, or direct operator input.",
        },
        "metrics": {
            "session_resume_time": {
                "sample_count": len(session_resume_samples),
                "summary": _duration_summary(session_resume_samples),
                "samples": session_resume_samples[:10],
            },
            "reopen_rate_after_verify": {
                "verified_task_count": reopen_denominator,
                "reopened_task_count": reopen_numerator,
                "rate": _ratio(reopen_numerator, reopen_denominator),
                "reopened_task_ids": sorted(reopened_task_ids),
            },
            "promotion_lead_time": {
                "sample_count": len(promotion_samples),
                "summary": _duration_summary(promotion_samples),
                "samples": promotion_samples[:10],
                "pending_task_count": _pending_promotion_count(tasks),
            },
            "manual_intervention_count": {
                "count": len(manual_events),
                "unique_task_count": len(
                    {
                        str(event.get("data", {}).get("task_id") or "")
                        for event in manual_events
                        if str(event.get("data", {}).get("task_id") or "").strip()
                    }
                ),
                "by_reason": dict(sorted(manual_reason_counts.items())),
                "pending_tasks": pending_manual_tasks[:20],
            },
        },
    }


def _metrics_event_paths(repo_root: Path, config: SisyphusConfig) -> list[Path]:
    bus_path = resolve_event_bus_path(repo_root, config)
    daemon_path = event_log_file(repo_root)
    ordered: list[Path] = []
    for candidate in (bus_path, daemon_path):
        if candidate in ordered:
            continue
        ordered.append(candidate)
    return ordered


def _read_metric_entries(paths: list[Path]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return sorted(entries, key=lambda entry: _parse_timestamp(entry.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))


def _emit_metric_event(repo_root: Path, config: SisyphusConfig, envelope) -> None:
    encoded = envelope.to_json()
    paths = {event_log_file(repo_root)}
    if str(config.event_bus.provider or "").strip().lower() not in {"", "noop", "none", "disabled"}:
        paths.add(resolve_event_bus_path(repo_root, config))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")


def _session_resume_samples(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    lifecycle: dict[str, dict[str, object]] = {}
    for entry in entries:
        if "status" not in entry:
            continue
        event_id = str(entry.get("event_id") or "").strip()
        status = str(entry.get("status") or "").strip()
        timestamp = _parse_timestamp(entry.get("timestamp"))
        if not event_id or timestamp is None:
            continue
        bucket = lifecycle.setdefault(
            event_id,
            {
                "event_id": event_id,
                "event_type": str(entry.get("event_type") or "").strip() or None,
                "queued_at": None,
                "processed_at": None,
            },
        )
        if status == "queued" and bucket["queued_at"] is None:
            bucket["queued_at"] = timestamp
        elif status == "processed" and bucket["processed_at"] is None:
            bucket["processed_at"] = timestamp

    samples: list[dict[str, object]] = []
    for event_id, bucket in lifecycle.items():
        queued_at = bucket.get("queued_at")
        processed_at = bucket.get("processed_at")
        if not isinstance(queued_at, datetime) or not isinstance(processed_at, datetime):
            continue
        seconds = (processed_at - queued_at).total_seconds()
        if seconds < 0:
            continue
        samples.append(
            {
                "event_id": event_id,
                "event_type": bucket.get("event_type"),
                "queued_at": _isoformat(queued_at),
                "processed_at": _isoformat(processed_at),
                "seconds": seconds,
            }
        )
    return samples


def _verified_task_ids(tasks: list[dict], entries: list[dict[str, object]]) -> set[str]:
    task_ids = {
        str(task.get("id"))
        for task in tasks
        if str(task.get("verify_status") or "").strip() == "passed" and str(task.get("last_verified_at") or "").strip()
    }
    for entry in entries:
        if str(entry.get("event_type") or "") != "verify.completed":
            continue
        data = entry.get("data", {})
        if not isinstance(data, dict):
            continue
        if str(data.get("status") or "") != "passed":
            continue
        task_id = str(data.get("task_id") or "").strip()
        if task_id:
            task_ids.add(task_id)
    return task_ids


def _reopened_after_verify_task_ids(tasks: list[dict], entries: list[dict[str, object]]) -> set[str]:
    task_ids = {
        str(task.get("id"))
        for task in tasks
        if bool(task.get("promotion", {}).get("reverify_required")) and str(task.get("last_verified_at") or "").strip()
    }
    for entry in entries:
        if str(entry.get("event_type") or "") != REOPENED_AFTER_VERIFY_EVENT:
            continue
        data = entry.get("data", {})
        if not isinstance(data, dict):
            continue
        task_id = str(data.get("task_id") or "").strip()
        if task_id:
            task_ids.add(task_id)
    return task_ids


def _promotion_lead_time_samples(tasks: list[dict]) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for task in tasks:
        promotion = task.get("promotion", {})
        if not isinstance(promotion, dict):
            continue
        verified_at = _parse_timestamp(task.get("last_verified_at"))
        recorded_at = _parse_timestamp(promotion.get("recorded_at") or promotion.get("merged_at"))
        if verified_at is None or recorded_at is None:
            continue
        seconds = (recorded_at - verified_at).total_seconds()
        if seconds < 0:
            continue
        samples.append(
            {
                "task_id": str(task.get("id")),
                "strategy": str(promotion.get("strategy") or "direct"),
                "verified_at": _isoformat(verified_at),
                "recorded_at": _isoformat(recorded_at),
                "seconds": seconds,
            }
        )
    return samples


def _manual_intervention_events(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        entry
        for entry in entries
        if str(entry.get("event_type") or "") == MANUAL_INTERVENTION_REQUIRED_EVENT
    ]


def _pending_promotion_count(tasks: list[dict]) -> int:
    count = 0
    for task in tasks:
        promotion = task.get("promotion", {})
        if not isinstance(promotion, dict):
            continue
        if not bool(promotion.get("required")):
            continue
        if str(task.get("last_verified_at") or "").strip() and not str(promotion.get("recorded_at") or "").strip():
            count += 1
    return count


def _duration_summary(samples: list[dict[str, object]]) -> dict[str, object]:
    seconds = [float(sample["seconds"]) for sample in samples if isinstance(sample.get("seconds"), (int, float))]
    if not seconds:
        return {
            "count": 0,
            "average_seconds": None,
            "median_seconds": None,
            "min_seconds": None,
            "max_seconds": None,
        }
    return {
        "count": len(seconds),
        "average_seconds": sum(seconds) / len(seconds),
        "median_seconds": median(seconds),
        "min_seconds": min(seconds),
        "max_seconds": max(seconds),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _parse_timestamp(raw: object) -> datetime | None:
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
