from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from ..application.codecs.events import encode_event_envelope_json
from ..application.events import new_event_envelope
from ..application.metrics import (
    MANUAL_INTERVENTION_REQUIRED_EVENT,
    REOPENED_AFTER_VERIFY_EVENT,
)
from ..shared.paths import event_log_file
from .config.loader import SisyphusConfig
from .events import append_jsonl_text, resolve_event_bus_path
from .persistence.file_lock import file_handle_lock


_READ_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def metric_event_paths(repo_root: Path, config: SisyphusConfig) -> list[Path]:
    ordered: list[Path] = []
    for candidate in (resolve_event_bus_path(repo_root, config), event_log_file(repo_root)):
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def read_metric_entries(paths: list[Path]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in paths:
        try:
            descriptor = os.open(path, _READ_FLAGS)
        except FileNotFoundError:
            continue
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle, file_handle_lock(handle):
            lines = handle.read().splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return sorted(
        entries,
        key=lambda entry: _parse_timestamp(entry.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc),
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
    data: dict[str, object] = {"task_id": task_id, "reason": reason}
    if workflow_phase:
        data["workflow_phase"] = workflow_phase
    if status:
        data["status"] = status
    if detail:
        data["detail"] = detail
    _emit_metric_event(
        repo_root,
        config,
        event_type=MANUAL_INTERVENTION_REQUIRED_EVENT,
        data=data,
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
    data: dict[str, object] = {"task_id": task_id, "reason": reason}
    if workflow_phase:
        data["workflow_phase"] = workflow_phase
    if previous_verify_status:
        data["previous_verify_status"] = previous_verify_status
    _emit_metric_event(
        repo_root,
        config,
        event_type=REOPENED_AFTER_VERIFY_EVENT,
        data=data,
    )


def _emit_metric_event(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    event_type: str,
    data: dict[str, object],
) -> None:
    envelope = new_event_envelope(
        event_type,
        source={"module": "metrics"},
        data=data,
    )
    paths = {event_log_file(repo_root)}
    if str(config.event_bus.provider or "").strip().lower() not in {
        "",
        "noop",
        "none",
        "disabled",
    }:
        paths.add(resolve_event_bus_path(repo_root, config))
    for path in paths:
        append_jsonl_text(path, encode_event_envelope_json(envelope))


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


__all__ = [
    "metric_event_paths",
    "publish_manual_intervention_required",
    "publish_reopened_after_verify",
    "read_metric_entries",
]
