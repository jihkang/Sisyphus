from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..bus_jsonl import read_jsonl_events, resolve_event_bus_path
from ..config import load_config
from ..conformance import summarize_task_conformance
from ..state import list_task_records


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class EvolutionVerifyTrace:
    command: str
    status: str
    exit_code: int | None
    output_excerpt: str | None
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True, slots=True)
class EvolutionTaskTrace:
    task_id: str
    slug: str
    task_type: str
    status: str
    workflow_phase: str | None
    plan_status: str | None
    spec_status: str | None
    verify_status: str | None
    updated_at: str | None
    last_verified_at: str | None
    subtask_count: int
    conformance_status: str
    drift_count: int
    unresolved_warning_count: int
    conformance_history_count: int
    verify_results: tuple[EvolutionVerifyTrace, ...]


@dataclass(frozen=True, slots=True)
class EvolutionEventTrace:
    event_id: str | None
    event_type: str | None
    timestamp: str | None
    status: str | None
    task_id: str | None
    source_module: str | None
    message: str | None


@dataclass(frozen=True, slots=True)
class EvolutionDataset:
    repo_root: str
    generated_at: str
    event_log_path: str
    selected_task_ids: tuple[str, ...]
    task_traces: tuple[EvolutionTaskTrace, ...]
    event_traces: tuple[EvolutionEventTrace, ...]

    @property
    def task_count(self) -> int:
        return len(self.task_traces)

    @property
    def event_count(self) -> int:
        return len(self.event_traces)


def build_evolution_dataset(
    repo_root: Path,
    *,
    task_ids: Sequence[str] | None = None,
    max_events: int = 50,
) -> EvolutionDataset:
    resolved_repo_root = repo_root.resolve()
    if not resolved_repo_root.exists():
        raise FileNotFoundError(f"repository root does not exist: {resolved_repo_root}")

    config = load_config(resolved_repo_root)
    tasks = sorted(
        list_task_records(repo_root=resolved_repo_root, task_dir_name=config.task_dir),
        key=lambda task: (str(task.get("updated_at") or ""), str(task.get("id") or "")),
    )
    selected_tasks = _select_tasks(tasks, task_ids)
    selected_task_ids = tuple(str(task.get("id")) for task in selected_tasks)

    event_log_path = resolve_event_bus_path(resolved_repo_root, config)
    raw_events = read_jsonl_events(event_log_path, limit=max_events)
    event_traces = tuple(
        _to_event_trace(event)
        for event in raw_events
        if task_ids is None or _event_task_id(event) in set(selected_task_ids)
    )

    return EvolutionDataset(
        repo_root=str(resolved_repo_root),
        generated_at=utc_now(),
        event_log_path=str(event_log_path),
        selected_task_ids=selected_task_ids,
        task_traces=tuple(_to_task_trace(task) for task in selected_tasks),
        event_traces=event_traces,
    )


def _select_tasks(tasks: list[dict], task_ids: Sequence[str] | None) -> list[dict]:
    if task_ids is None:
        return tasks

    normalized_ids = [str(task_id).strip() for task_id in task_ids if str(task_id).strip()]
    if not normalized_ids:
        raise ValueError("dataset extraction requires at least one task id when an explicit selection is provided")

    available_ids = {str(task.get("id")) for task in tasks}
    requested_ids = set(normalized_ids)
    unknown_ids = sorted(requested_ids - available_ids)
    if unknown_ids:
        raise ValueError(f"unknown task ids: {', '.join(unknown_ids)}")
    return [task for task in tasks if str(task.get("id")) in requested_ids]


def _to_task_trace(task: dict) -> EvolutionTaskTrace:
    conformance = summarize_task_conformance(task)
    history = task.get("conformance", {}).get("history", [])
    if not isinstance(history, list):
        history = []
    subtasks = task.get("subtasks", [])
    if not isinstance(subtasks, list):
        subtasks = []
    verify_results = task.get("last_verify_results", [])
    if not isinstance(verify_results, list):
        verify_results = []

    return EvolutionTaskTrace(
        task_id=str(task.get("id") or ""),
        slug=str(task.get("slug") or ""),
        task_type=str(task.get("type") or ""),
        status=str(task.get("status") or ""),
        workflow_phase=_optional_str(task.get("workflow_phase")),
        plan_status=_optional_str(task.get("plan_status")),
        spec_status=_optional_str(task.get("spec_status")),
        verify_status=_optional_str(task.get("verify_status")),
        updated_at=_optional_str(task.get("updated_at")),
        last_verified_at=_optional_str(task.get("last_verified_at")),
        subtask_count=len(subtasks),
        conformance_status=str(conformance.get("status") or ""),
        drift_count=int(conformance.get("drift_count", 0)),
        unresolved_warning_count=int(conformance.get("unresolved_warning_count", 0)),
        conformance_history_count=len(history),
        verify_results=tuple(_to_verify_trace(result) for result in verify_results if isinstance(result, Mapping)),
    )


def _to_verify_trace(result: Mapping[str, object]) -> EvolutionVerifyTrace:
    exit_code = result.get("exit_code")
    return EvolutionVerifyTrace(
        command=str(result.get("command") or result.get("name") or ""),
        status=str(result.get("status") or ""),
        exit_code=int(exit_code) if isinstance(exit_code, int) else None,
        output_excerpt=_optional_str(result.get("output_excerpt")),
        started_at=_optional_str(result.get("started_at")),
        finished_at=_optional_str(result.get("finished_at")),
    )


def _to_event_trace(event: Mapping[str, object]) -> EvolutionEventTrace:
    source = event.get("source", {})
    source_module = None
    if isinstance(source, Mapping):
        source_module = _optional_str(source.get("module"))

    return EvolutionEventTrace(
        event_id=_optional_str(event.get("event_id")),
        event_type=_optional_str(event.get("event_type")),
        timestamp=_optional_str(event.get("timestamp")),
        status=_optional_str(event.get("status")),
        task_id=_event_task_id(event),
        source_module=source_module,
        message=_optional_str(event.get("message")),
    )


def _event_task_id(event: Mapping[str, object]) -> str | None:
    data = event.get("data", {})
    if isinstance(data, Mapping):
        task_id = _optional_str(data.get("task_id"))
        if task_id:
            return task_id

    result = event.get("result", {})
    if isinstance(result, Mapping):
        task_id = _optional_str(result.get("task_id"))
        if task_id:
            return task_id

    return None


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
