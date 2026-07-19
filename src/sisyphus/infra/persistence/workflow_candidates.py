from __future__ import annotations

from pathlib import Path
from typing import cast

from ...domain.planning.models import PlanStatus, normalize_plan_status
from ...shared.paths import workflow_candidate_index_file
from .json_store import read_json_file, write_json_file
from .task_repository import normalize_task_projection


WORKFLOW_CANDIDATE_INDEX_SCHEMA = "sisyphus.workflow_candidate_index.v1"
_BLOCKED_PHASES = {"needs_user_input", "promotion_pending", "retarget_required"}


def list_workflow_candidate_ids(repo_root: Path, task_dir_name: str) -> list[str]:
    task_root = repo_root / task_dir_name
    index_path = workflow_candidate_index_file(repo_root)
    cached_entries, cache_valid = _read_index(index_path, task_dir_name=task_dir_name)
    current_entries: dict[str, dict[str, object]] = {}
    changed = not cache_valid

    if task_root.exists():
        for task_file in task_root.glob("*/task.json"):
            try:
                stat = task_file.stat()
            except FileNotFoundError:
                continue
            relative_path = task_file.relative_to(task_root).as_posix()
            fingerprint = {
                "mtime_ns": stat.st_mtime_ns,
                "ctime_ns": stat.st_ctime_ns,
                "size": stat.st_size,
            }
            cached = cached_entries.get(relative_path)
            if cached is not None and _matches_fingerprint(cached, fingerprint):
                current_entries[relative_path] = cached
                continue
            current_entries[relative_path] = _project_entry(
                task_file,
                relative_path=relative_path,
                fingerprint=fingerprint,
            )
            changed = True

    if set(current_entries) != set(cached_entries):
        changed = True

    ordered_entries = {path: current_entries[path] for path in sorted(current_entries)}
    if changed:
        _write_index(
            index_path,
            task_dir_name=task_dir_name,
            entries=ordered_entries,
        )

    candidates = [entry for entry in ordered_entries.values() if entry.get("eligible") is True]
    candidates.sort(key=lambda entry: (str(entry.get("updated_at") or ""), str(entry.get("task_id") or "")))
    return [str(entry["task_id"]) for entry in candidates]


def is_workflow_candidate(task: dict[str, object]) -> bool:
    meta = task.get("meta")
    auto_loop_enabled = meta.get("auto_loop_enabled", True) if isinstance(meta, dict) else True
    if not bool(auto_loop_enabled):
        return False
    if task.get("status") == "closed":
        return False
    if str(task.get("workflow_phase") or "") in _BLOCKED_PHASES:
        return False
    return normalize_plan_status(task.get("plan_status")) == PlanStatus.APPROVED


def _project_entry(
    task_file: Path,
    *,
    relative_path: str,
    fingerprint: dict[str, int],
) -> dict[str, object]:
    task_id = task_file.parent.name
    updated_at = ""
    eligible = False
    valid = False
    try:
        raw = read_json_file(task_file)
        if not isinstance(raw, dict):
            raise ValueError("task record must be an object")
        task = normalize_task_projection(raw, task_file=task_file, sync_strategy=False)
        projected_id = task.get("id")
        if not isinstance(projected_id, str) or not projected_id.strip():
            raise ValueError("task record requires a non-empty id")
        if projected_id != task_file.parent.name:
            raise ValueError("task id must match its task directory")
        task_id = projected_id
        updated_at = str(task.get("updated_at") or "")
        eligible = is_workflow_candidate(cast(dict[str, object], task))
        valid = True
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        # Keep malformed records ineligible until their fingerprint changes.
        pass
    return {
        "path": relative_path,
        **fingerprint,
        "task_id": task_id,
        "updated_at": updated_at,
        "eligible": eligible,
        "valid": valid,
    }


def _read_index(index_path: Path, *, task_dir_name: str) -> tuple[dict[str, dict[str, object]], bool]:
    if not index_path.exists():
        return {}, False
    try:
        raw = read_json_file(index_path)
    except (OSError, UnicodeError, ValueError):
        return {}, False
    if not isinstance(raw, dict):
        return {}, False
    if raw.get("schema_version") != WORKFLOW_CANDIDATE_INDEX_SCHEMA:
        return {}, False
    if raw.get("task_dir") != _normalized_task_dir(task_dir_name):
        return {}, False
    raw_entries = raw.get("entries")
    if not isinstance(raw_entries, dict):
        return {}, False

    entries: dict[str, dict[str, object]] = {}
    for path, raw_entry in raw_entries.items():
        if not isinstance(path, str) or not _valid_entry(raw_entry, relative_path=path):
            return {}, False
        entries[path] = cast(dict[str, object], raw_entry)
    return entries, True


def _valid_entry(raw: object, *, relative_path: str) -> bool:
    if not isinstance(raw, dict) or raw.get("path") != relative_path:
        return False
    for key in ("mtime_ns", "ctime_ns", "size"):
        if type(raw.get(key)) is not int or int(raw[key]) < 0:
            return False
    expected_task_id = Path(relative_path).parent.name
    if raw.get("task_id") != expected_task_id or not isinstance(raw.get("updated_at"), str):
        return False
    if type(raw.get("eligible")) is not bool or type(raw.get("valid")) is not bool:
        return False
    return True


def _matches_fingerprint(entry: dict[str, object], fingerprint: dict[str, int]) -> bool:
    return all(entry.get(key) == value for key, value in fingerprint.items())


def _write_index(
    index_path: Path,
    *,
    task_dir_name: str,
    entries: dict[str, dict[str, object]],
) -> None:
    try:
        write_json_file(
            index_path,
            {
                "schema_version": WORKFLOW_CANDIDATE_INDEX_SCHEMA,
                "task_dir": _normalized_task_dir(task_dir_name),
                "entries": entries,
            },
        )
    except OSError:
        # This cache is an optimization; a write failure must not block scheduling.
        pass


def _normalized_task_dir(task_dir_name: str) -> str:
    return Path(task_dir_name).as_posix().rstrip("/")


__all__ = [
    "WORKFLOW_CANDIDATE_INDEX_SCHEMA",
    "is_workflow_candidate",
    "list_workflow_candidate_ids",
]
