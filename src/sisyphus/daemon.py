from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import time
import uuid

from .bus import build_event_publisher
from .config import SisyphusConfig, load_config
from .creation import create_task_workspace
from .gitops import copy_relative_path, current_branch_name, list_dirty_paths, remove_relative_path
from .events import new_event_envelope
from .metrics import publish_manual_intervention_required
from .paths import event_log_file, inbox_failed_dir, inbox_pending_dir, inbox_processed_dir
from .planning import enforce_plan_approved, enforce_spec_frozen
from .promotion import record_merged_pull_request
from .provider_wrapper import run_provider_wrapper
from .state import list_task_records, load_task_record, save_task_record, sync_task_support_files, utc_now
from .utils import project_fields
from .workflow import run_workflow_cycle


CONVERSATION_FIELD_DEFAULTS = {
    "title": "",
    "message": "",
    "task_type": "feature",
    "slug": "",
    "instruction": None,
    "agent_id": "worker-1",
    "role": "worker",
    "provider": "codex",
    "owned_paths": list,
    "provider_args": list,
    "source_context": dict,
    "adopt_current_changes": False,
    "adopt_paths": list,
    "auto_run": True,
}

PULL_REQUEST_MERGED_FIELD_DEFAULTS = {
    "task_id": None,
    "branch": None,
    "repo_full_name": None,
    "pr_number": None,
    "title": "",
    "url": None,
    "base_branch": None,
    "head_branch": None,
    "head_sha": None,
    "merge_commit_sha": None,
    "merged_at": None,
    "merged_by": None,
    "merge_method": None,
    "additions": None,
    "deletions": None,
    "changed_files": list,
}


@dataclass(slots=True)
class DaemonStats:
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    orchestrated: int = 0


class DaemonError(RuntimeError):
    """Raised when inbox processing cannot continue safely."""


def queue_conversation_event(
    repo_root: Path,
    *,
    message: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    source_context: dict[str, object] | None = None,
    adopt_current_changes: bool = False,
    adopt_paths: list[str] | None = None,
    auto_run: bool = True,
) -> tuple[dict, Path]:
    event_id = _new_event_id()
    normalized_title = (title or "").strip()
    normalized_message = message.strip()
    if not normalized_message:
        raise DaemonError("conversation event requires a non-empty message")
    if task_type not in {"feature", "issue"}:
        raise DaemonError(f"unsupported task type: {task_type}")

    payload = project_fields(
        {
            "title": normalized_title,
            "message": normalized_message,
            "task_type": task_type,
            "slug": (slug or "").strip(),
            "instruction": instruction,
            "agent_id": agent_id,
            "role": role,
            "provider": provider,
            "owned_paths": owned_paths or [],
            "provider_args": provider_args or [],
            "source_context": source_context or {},
            "adopt_current_changes": adopt_current_changes,
            "adopt_paths": adopt_paths or [],
            "auto_run": auto_run,
        },
        CONVERSATION_FIELD_DEFAULTS,
    )
    payload["title"] = payload["title"] or _title_from_message(payload["message"])
    payload["slug"] = payload["slug"] or _slugify(payload["title"], fallback=f"conversation-task-{event_id[-4:]}")

    event = {
        "id": event_id,
        "event_type": "conversation",
        "status": "queued",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "payload": payload,
        "result": None,
        "error": None,
    }
    target_dir = inbox_pending_dir(repo_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    event_path = target_dir / f"{event_id}.json"
    event_path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    _append_event_log(
        repo_root,
        {
            "timestamp": utc_now(),
            "event_id": event_id,
            "event_type": "conversation",
            "status": "queued",
            "message": "conversation event queued",
        },
    )
    build_event_publisher(repo_root, load_config(repo_root)).publish(
        new_event_envelope(
            "conversation.queued",
            source={"module": "daemon"},
            data={"event_id": event_id, "task_type": task_type, "slug": payload["slug"]},
        )
    )
    return event, event_path


def queue_pull_request_merged_event(
    repo_root: Path,
    *,
    pr_number: int,
    title: str,
    task_id: str | None = None,
    branch: str | None = None,
    repo_full_name: str | None = None,
    url: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    head_sha: str | None = None,
    merge_commit_sha: str | None = None,
    merged_at: str | None = None,
    merged_by: str | None = None,
    merge_method: str | None = None,
    additions: int | None = None,
    deletions: int | None = None,
    changed_files: list[dict[str, object]] | None = None,
) -> tuple[dict, Path]:
    if pr_number < 1:
        raise DaemonError("pull request merge event requires a positive pr_number")
    normalized_title = title.strip()
    if not normalized_title:
        raise DaemonError("pull request merge event requires a non-empty title")
    normalized_branch = (branch or head_branch or "").strip()
    if not normalized_branch and not (task_id or "").strip():
        raise DaemonError("pull request merge event requires task_id or branch/head_branch")

    normalized_changed_files: list[dict[str, object]] = []
    for item in changed_files or []:
        if not isinstance(item, dict):
            raise DaemonError("changed_files entries must be mapping objects")
        normalized_changed_files.append(dict(item))

    payload = project_fields(
        {
            "task_id": (task_id or "").strip() or None,
            "branch": normalized_branch or None,
            "repo_full_name": (repo_full_name or "").strip() or None,
            "pr_number": pr_number,
            "title": normalized_title,
            "url": (url or "").strip() or None,
            "base_branch": (base_branch or "").strip() or None,
            "head_branch": (head_branch or "").strip() or None,
            "head_sha": (head_sha or "").strip() or None,
            "merge_commit_sha": (merge_commit_sha or "").strip() or None,
            "merged_at": (merged_at or "").strip() or None,
            "merged_by": (merged_by or "").strip() or None,
            "merge_method": (merge_method or "").strip() or None,
            "additions": additions,
            "deletions": deletions,
            "changed_files": normalized_changed_files,
        },
        PULL_REQUEST_MERGED_FIELD_DEFAULTS,
    )

    event_id = _new_event_id()
    event = {
        "id": event_id,
        "event_type": "pull_request_merged",
        "status": "queued",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "payload": payload,
        "result": None,
        "error": None,
    }
    target_dir = inbox_pending_dir(repo_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    event_path = target_dir / f"{event_id}.json"
    event_path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    _append_event_log(
        repo_root,
        {
            "timestamp": utc_now(),
            "event_id": event_id,
            "event_type": "pull_request_merged",
            "status": "queued",
            "message": f"pull request merge event queued for pr #{pr_number}",
        },
    )
    build_event_publisher(repo_root, load_config(repo_root)).publish(
        new_event_envelope(
            "pull_request.merged.queued",
            source={"module": "daemon"},
            data={
                "event_id": event_id,
                "task_id": payload.get("task_id"),
                "branch": payload.get("branch"),
                "pr_number": pr_number,
            },
        )
    )
    return event, event_path


def run_daemon(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    once: bool,
    poll_interval_seconds: int,
    max_events: int | None = None,
) -> DaemonStats:
    stats = DaemonStats()
    while True:
        available = sorted(inbox_pending_dir(repo_root).glob("*.json"))
        progressed = False

        for event_path in available:
            process_inbox_event(repo_root=repo_root, config=config, event_path=event_path, stats=stats)
            progressed = True
            if max_events is not None and (stats.processed + stats.failed) >= max_events:
                return stats

        orchestrated = run_workflow_cycle(repo_root=repo_root, config=config)
        if orchestrated:
            stats.orchestrated += orchestrated
            progressed = True

        if once and not progressed:
            return stats
        if once:
            continue
        if not progressed:
            time.sleep(max(poll_interval_seconds, 1))


def process_inbox_event(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    event_path: Path,
    stats: DaemonStats | None = None,
) -> dict:
    publisher = build_event_publisher(repo_root, config)
    raw_content = event_path.read_text(encoding="utf-8")
    event = json.loads(raw_content)
    event["status"] = "processing"
    event["updated_at"] = utc_now()
    event_path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    _append_event_log(
        repo_root,
        {
            "timestamp": utc_now(),
            "event_id": event.get("id"),
            "event_type": event.get("event_type"),
            "status": "processing",
            "message": f"processing {event_path.name}",
        },
    )

    try:
        event_type = str(event.get("event_type"))
        if event_type == "conversation":
            result = _process_conversation_event(repo_root=repo_root, config=config, event=event)
        elif event_type == "pull_request_merged":
            result = _process_pull_request_merged_event(repo_root=repo_root, config=config, event=event)
        else:
            raise DaemonError(f"unsupported event type: {event.get('event_type')}")
        event["status"] = "processed"
        event["updated_at"] = utc_now()
        event["result"] = result
        event["error"] = None
        destination = inbox_processed_dir(repo_root) / event_path.name
        if stats is not None:
            stats.processed += 1
        success_message = (
            f"created task {result['task_id']}"
            if event_type == "conversation"
            else f"recorded merge receipt for task {result['task_id']}"
        )
        _append_event_log(
            repo_root,
            {
                "timestamp": utc_now(),
                "event_id": event.get("id"),
                "event_type": event.get("event_type"),
                "status": "processed",
                "message": success_message,
                "result": result,
            },
        )
        processed_envelope_type = "conversation.processed" if event_type == "conversation" else "pull_request.merged.processed"
        processed_data = {"event_id": event.get("id"), "task_id": result.get("task_id"), "status": "processed"}
        if event_type == "pull_request_merged":
            processed_data["pr_number"] = result.get("pr_number")
        publisher.publish(
            new_event_envelope(
                processed_envelope_type,
                source={"module": "daemon"},
                data=processed_data,
            )
        )
    except Exception as exc:
        event_type = str(event.get("event_type"))
        event["status"] = "failed"
        event["updated_at"] = utc_now()
        event["error"] = str(exc)
        destination = inbox_failed_dir(repo_root) / event_path.name
        if stats is not None:
            stats.failed += 1
        _append_event_log(
            repo_root,
            {
                "timestamp": utc_now(),
                "event_id": event.get("id"),
                "event_type": event.get("event_type"),
                "status": "failed",
                "message": str(exc),
            },
        )
        failed_envelope_type = "conversation.failed" if event_type == "conversation" else "pull_request.merged.failed"
        publisher.publish(
            new_event_envelope(
                failed_envelope_type,
                source={"module": "daemon"},
                data={"event_id": event.get("id"), "status": "failed", "error": str(exc)},
            )
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    event_path.unlink()
    return event


def _process_conversation_event(repo_root: Path, config: SisyphusConfig, event: dict) -> dict:
    publisher = build_event_publisher(repo_root, config)
    payload = project_fields(event.get("payload", {}), CONVERSATION_FIELD_DEFAULTS)
    title = str(payload["title"]).strip()
    message = str(payload["message"]).strip()
    task_type = str(payload["task_type"]).strip()
    requested_slug = str(payload["slug"]).strip() or _slugify(title or message, fallback=f"conversation-task-{event['id'][-4:]}")
    slug, parent_task_id = _resolve_followup_slug(
        repo_root=repo_root,
        config=config,
        task_type=task_type,
        requested_slug=requested_slug,
    )
    provider = str(payload["provider"]).strip() or "codex"
    role = str(payload["role"]).strip() or "worker"
    instruction = payload["instruction"]
    agent_id = str(payload["agent_id"]).strip() or "worker-1"
    owned_paths = [str(path) for path in payload["owned_paths"]]
    provider_args = [str(arg) for arg in payload["provider_args"]]
    source_context = dict(payload["source_context"])
    adopt_current_changes = bool(payload["adopt_current_changes"])
    requested_adopt_paths = [str(path) for path in payload["adopt_paths"]]
    auto_run = bool(payload["auto_run"])
    requested_auto_run = auto_run

    outcome = create_task_workspace(
        repo_root=repo_root,
        config=config,
        task_type=task_type,
        slug=slug,
    )
    task = outcome.task
    _hydrate_task_from_conversation(
        task=task,
        title=title,
        message=message,
        event_id=event["id"],
        provider=provider,
        auto_loop_enabled=requested_auto_run,
        source_context=source_context,
        owned_paths=owned_paths,
        requested_adopt_paths=requested_adopt_paths,
        requested_slug=requested_slug,
        parent_task_id=parent_task_id,
    )
    if adopt_current_changes:
        _apply_direct_change_adoption(
            repo_root=repo_root,
            config=config,
            task_id=task["id"],
            requested_paths=requested_adopt_paths,
        )
        task, _ = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task["id"])
    publisher.publish(
        new_event_envelope(
            "task.created",
            source={"module": "daemon"},
            data={
                "task_id": task["id"],
                "task_type": task["type"],
                "slug": task["slug"],
                "branch": task["branch"],
                "worktree_path": task["worktree_path"],
            },
        )
    )
    publish_manual_intervention_required(
        repo_root,
        config,
        task_id=str(task["id"]),
        reason="plan_review_required",
        workflow_phase="plan_in_review",
        status=str(task.get("status") or ""),
        detail="new task creation starts in plan review",
    )

    agent_exit_code = None
    blocked_reason = None
    if auto_run:
        approved, task = enforce_plan_approved(
            repo_root=repo_root,
            config=config,
            task_id=task["id"],
            action="auto-run",
        )
        if approved:
            frozen, task = enforce_spec_frozen(
                repo_root=repo_root,
                config=config,
                task_id=task["id"],
                action="auto-run",
            )
            if frozen:
                wrapper_args = [task["id"], agent_id, "--role", role]
                if instruction:
                    wrapper_args.extend(["--instruction", str(instruction)])
                for path in owned_paths:
                    wrapper_args.extend(["--owned-path", path])
                for arg in provider_args:
                    wrapper_args.extend(["--provider-arg", arg])
                agent_exit_code = run_provider_wrapper(provider, wrapper_args, repo_root=repo_root)
                if agent_exit_code != 0:
                    raise DaemonError(f"{provider} worker exited with code {agent_exit_code}")
            else:
                auto_run = False
                blocked_reason = "task spec must be frozen before auto-run"
        else:
            auto_run = False
            blocked_reason = "task plan must be approved before auto-run"

    if blocked_reason:
        publisher.publish(
            new_event_envelope(
                "task.blocked",
                source={"module": "daemon"},
                data={"task_id": task["id"], "reason": blocked_reason},
            )
        )

    return {
        "task_id": task["id"],
        "task_type": task["type"],
        "slug": task["slug"],
        "requested_slug": requested_slug,
        "followup_of_task_id": parent_task_id,
        "branch": task["branch"],
        "worktree_path": task["worktree_path"],
        "agent_id": agent_id if auto_run else None,
        "agent_exit_code": agent_exit_code,
        "auto_run": auto_run,
        "plan_status": task.get("plan_status"),
        "spec_status": task.get("spec_status"),
        "blocked_reason": blocked_reason,
    }


def _process_pull_request_merged_event(repo_root: Path, config: SisyphusConfig, event: dict) -> dict:
    publisher = build_event_publisher(repo_root, config)
    payload = project_fields(event.get("payload", {}), PULL_REQUEST_MERGED_FIELD_DEFAULTS)
    outcome = record_merged_pull_request(
        repo_root=repo_root,
        config=config,
        task_id=str(payload["task_id"]) if payload.get("task_id") else None,
        branch=str(payload["branch"]) if payload.get("branch") else None,
        repo_full_name=str(payload["repo_full_name"]) if payload.get("repo_full_name") else None,
        pr_number=int(payload["pr_number"]),
        title=str(payload["title"]),
        url=str(payload["url"]) if payload.get("url") else None,
        base_branch=str(payload["base_branch"]) if payload.get("base_branch") else None,
        head_branch=str(payload["head_branch"]) if payload.get("head_branch") else None,
        head_sha=str(payload["head_sha"]) if payload.get("head_sha") else None,
        merge_commit_sha=str(payload["merge_commit_sha"]) if payload.get("merge_commit_sha") else None,
        merged_at=str(payload["merged_at"]) if payload.get("merged_at") else None,
        merged_by=str(payload["merged_by"]) if payload.get("merged_by") else None,
        merge_method=str(payload["merge_method"]) if payload.get("merge_method") else None,
        additions=int(payload["additions"]) if payload.get("additions") is not None else None,
        deletions=int(payload["deletions"]) if payload.get("deletions") is not None else None,
        changed_files=[dict(item) for item in payload.get("changed_files", []) if isinstance(item, dict)],
    )
    publisher.publish(
        new_event_envelope(
            "promotion.recorded",
            source={"module": "daemon"},
            data={
                "promotion_kind": "pull_request_merge",
                "task_id": outcome.task_id,
                "branch": outcome.branch,
                "pr_number": outcome.pr_number,
                "title": outcome.title,
                "recorded_at": outcome.recorded_at,
                "receipt_path": str(outcome.receipt_path),
                "changeset_path": str(outcome.changeset_path),
                "close_attempted": outcome.close_attempted,
                "closed": outcome.closed,
                "close_status": outcome.close_status,
                "close_gate_codes": list(outcome.close_gate_codes),
                "child_retargeted_task_ids": list(outcome.child_retargeted_task_ids),
            },
        )
    )
    return {
        "task_id": outcome.task_id,
        "branch": outcome.branch,
        "pr_number": outcome.pr_number,
        "title": outcome.title,
        "recorded_at": outcome.recorded_at,
        "receipt_path": str(outcome.receipt_path),
        "changeset_path": str(outcome.changeset_path),
        "close_attempted": outcome.close_attempted,
        "closed": outcome.closed,
        "close_status": outcome.close_status,
        "close_gate_codes": list(outcome.close_gate_codes),
        "child_retargeted_task_ids": list(outcome.child_retargeted_task_ids),
    }


def _hydrate_task_from_conversation(
    task: dict,
    *,
    title: str,
    message: str,
    event_id: str,
    provider: str,
    auto_loop_enabled: bool,
    source_context: dict[str, object],
    owned_paths: list[str],
    requested_adopt_paths: list[str],
    requested_slug: str,
    parent_task_id: str | None,
) -> None:
    repo_root = Path(task["repo_root"])
    task_dir = repo_root / task["task_dir"]
    title_line = title or _title_from_message(message)

    brief_path = task_dir / task["docs"]["brief"]
    brief_path.write_text(
        _render_brief(
            task,
            title_line,
            message,
            requested_slug=requested_slug,
            parent_task_id=parent_task_id,
        ),
        encoding="utf-8",
    )

    if task["type"] == "feature":
        plan_path = task_dir / task["docs"]["plan"]
        plan_path.write_text(_render_feature_plan(task, title_line, message), encoding="utf-8")
    else:
        repro_path = task_dir / task["docs"]["repro"]
        repro_path.write_text(_render_issue_repro(task, title_line, message), encoding="utf-8")
        fix_plan_path = task_dir / task["docs"]["fix_plan"]
        fix_plan_path.write_text(_render_issue_fix_plan(task, title_line, message), encoding="utf-8")

    task_record, task_file = load_task_record(repo_root, task_dir_name=str(Path(task["task_dir"]).parent), task_id=task["id"])
    task_record.setdefault("meta", {})
    task_record["meta"]["source_event_id"] = event_id
    task_record["meta"]["source_event_type"] = "conversation"
    task_record["meta"]["default_provider"] = provider
    task_record["meta"]["auto_loop_enabled"] = auto_loop_enabled
    task_record["meta"]["requested_slug"] = requested_slug
    task_record["meta"]["owned_paths"] = list(owned_paths)
    task_record["meta"]["requested_adopt_paths"] = list(requested_adopt_paths)
    if parent_task_id:
        task_record["meta"]["followup_of_task_id"] = parent_task_id
    if source_context:
        task_record["meta"]["source_context"] = source_context
    save_task_record(task_file=task_file, task=task_record)
    sync_task_support_files(task_record)


def _apply_direct_change_adoption(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    requested_paths: list[str],
) -> None:
    task, task_file = load_task_record(repo_root, task_dir_name=config.task_dir, task_id=task_id)
    source_branch = current_branch_name(repo_root)
    changed_paths, deleted_paths = list_dirty_paths(repo_root)
    changed_paths = [path for path in changed_paths if not _is_internal_sisyphus_path(path)]
    deleted_paths = [path for path in deleted_paths if not _is_internal_sisyphus_path(path)]
    selected_changed = _select_adopt_paths(changed_paths, requested_paths)
    selected_deleted = _select_adopt_paths(deleted_paths, requested_paths)

    adopted_paths: list[str] = []
    worktree_root = Path(task["worktree_path"])
    for relative_path in selected_changed:
        source_path = repo_root / relative_path
        if not source_path.exists():
            continue
        copy_relative_path(repo_root, worktree_root, relative_path)
        if relative_path not in adopted_paths:
            adopted_paths.append(relative_path)

    for relative_path in selected_deleted:
        remove_relative_path(worktree_root, relative_path)
        if relative_path not in adopted_paths:
            adopted_paths.append(relative_path)

    task.setdefault("meta", {})
    task["meta"]["adopted_changes"] = {
        "source_branch": source_branch,
        "source_repo_root": str(repo_root),
        "paths": adopted_paths,
        "requested_paths": requested_paths,
        "deleted_paths": selected_deleted,
        "applied_at": utc_now(),
    }
    save_task_record(task_file=task_file, task=task)
    _append_task_log_note(
        repo_root=repo_root,
        task=task,
        note=_render_adoption_log_note(source_branch=source_branch, adopted_paths=adopted_paths, deleted_paths=selected_deleted),
    )
    sync_task_support_files(task)


def _resolve_followup_slug(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_type: str,
    requested_slug: str,
) -> tuple[str, str | None]:
    matching = [
        task
        for task in list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
        if str(task.get("type")) == task_type and str(task.get("slug")) == requested_slug
    ]
    if not matching:
        return requested_slug, None

    latest = sorted(
        matching,
        key=lambda task: (
            str(task.get("updated_at", "")),
            str(task.get("created_at", "")),
            str(task.get("id", "")),
        ),
    )[-1]
    if str(latest.get("status")) != "closed":
        return requested_slug, None

    sibling_slugs = {
        str(task.get("slug"))
        for task in list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
        if str(task.get("type")) == task_type
    }
    return _next_followup_slug(requested_slug, sibling_slugs), str(latest.get("id"))


def _next_followup_slug(requested_slug: str, sibling_slugs: set[str]) -> str:
    base = f"{requested_slug}-followup"
    if base not in sibling_slugs:
        return base

    index = 2
    while True:
        candidate = f"{base}-{index}"
        if candidate not in sibling_slugs:
            return candidate
        index += 1


def _select_adopt_paths(paths: list[str], requested_paths: list[str]) -> list[str]:
    if not requested_paths:
        return list(paths)
    selected: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        for requested in requested_paths:
            prefix = requested.replace("\\", "/").rstrip("/")
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                selected.append(path)
                break
    return selected


def _append_task_log_note(*, repo_root: Path, task: dict, note: str) -> None:
    task_dir = repo_root / task["task_dir"]
    log_relative = task.get("docs", {}).get("log")
    if not log_relative:
        return
    log_path = task_dir / str(log_relative)
    if not log_path.exists():
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    try:
        index = lines.index("## Notes")
    except ValueError:
        log_path.write_text(log_path.read_text(encoding="utf-8").rstrip() + f"\n\n## Notes\n\n- {note}\n", encoding="utf-8")
        return

    insertion_index = index + 1
    while insertion_index < len(lines) and not lines[insertion_index].startswith("## "):
        insertion_index += 1
    lines[insertion_index:insertion_index] = ["", f"- {note}"]
    log_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _render_adoption_log_note(*, source_branch: str | None, adopted_paths: list[str], deleted_paths: list[str]) -> str:
    branch_label = source_branch or "detached"
    path_count = len(adopted_paths)
    deleted_count = len(deleted_paths)
    if deleted_count:
        return f"Adopted {path_count} current changes from branch `{branch_label}` into the task worktree, including {deleted_count} deletions."
    return f"Adopted {path_count} current changes from branch `{branch_label}` into the task worktree."


def _is_internal_sisyphus_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return normalized == ".planning" or normalized.startswith(".planning/")


def _render_brief(
    task: dict,
    title: str,
    message: str,
    *,
    requested_slug: str,
    parent_task_id: str | None,
) -> str:
    lines = [
        "# Brief",
        "",
        "## Task",
        "",
        f"- Task ID: `{task['id']}`",
        f"- Type: `{task['type']}`",
        f"- Slug: `{task['slug']}`",
        f"- Branch: `{task['branch']}`",
    ]
    if requested_slug and requested_slug != str(task["slug"]):
        lines.append(f"- Requested Slug: `{requested_slug}`")
    if parent_task_id:
        lines.append(f"- Follow-up Of: `{parent_task_id}`")
    lines.extend(
        [
            "",
            "## Problem" if task["type"] == "feature" else "## Symptom",
            "",
            f"- {title}",
            f"- Original request: {message}",
        ]
    )
    if parent_task_id:
        lines.append(f"- This task continues implementation work after `{parent_task_id}` was closed.")
    lines.extend(
        [
            "",
            "## Desired Outcome" if task["type"] == "feature" else "## Expected Behavior",
            "",
            "- The repository behavior matches the requested conversation outcome.",
            "- The resulting change stays scoped to this task branch and worktree.",
            "",
            "## Acceptance Criteria" if task["type"] == "feature" else "## Impact",
            "",
            "- [ ] The requested workflow is implemented or corrected.",
            "- [ ] The task docs reflect the actual implementation and verification scope.",
            "- [ ] Verification notes are ready to be updated after implementation.",
            "",
            "## Constraints" if task["type"] == "feature" else "## Notes",
            "",
            "- Preserve existing repository conventions unless the task requires a deliberate change.",
            "- Re-read the task docs before verify and close.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_feature_plan(task: dict, title: str, message: str) -> str:
    request_summary = _single_line(message)
    return "\n".join(
        [
            "# Plan",
            "",
            "## Implementation Plan",
            "",
            f"1. Inspect the current code path related to: {title}.",
            f"2. Implement the requested behavior for: {request_summary}.",
            "3. Update tests and task docs to match the final behavior.",
            "",
            "## Risks",
            "",
            "- The conversation request may omit edge conditions that still matter in the current codebase.",
            "- The change may affect adjacent flows if the requested behavior touches shared state.",
            "",
            "## Design Evaluation",
            "",
            "- Design Mode: `none`",
            "- Decision Reason: `existing contract only`",
            "- Confidence: `medium`",
            "- Layer Impact: `layer-preserving`",
            "- Layer Decision Reason: `n/a`",
            "- Required Design Artifacts: `none`",
            "",
            "## Design Artifacts",
            "",
            "- Connection Diagram: `n/a`",
            "- Sequence Diagram: `n/a`",
            "- Boundary Note: `n/a`",
            "",
            "## Test Strategy",
            "",
            "### Normal Cases",
            "",
            "- [ ] Requested conversation workflow succeeds",
            "",
            "### Edge Cases",
            "",
            "- [ ] Minimal valid input still behaves predictably",
            "",
            "### Exception Cases",
            "",
            "- [ ] Unexpected failure surfaces an actionable error",
            "",
            "## Verification Mapping",
            "",
            "- `Requested conversation workflow succeeds` -> `sisyphus verify`",
            "- `Minimal valid input still behaves predictably` -> `targeted regression test`",
            "- `Unexpected failure surfaces an actionable error` -> `manual review`",
            "",
            "## External LLM Review",
            "",
            "- Required: `no`",
            "- Provider: `n/a`",
            "- Purpose: `n/a`",
            "- Trigger: `n/a`",
            "",
        ]
    )


def _render_issue_repro(task: dict, title: str, message: str) -> str:
    return "\n".join(
        [
            "# Repro",
            "",
            "## Preconditions",
            "",
            "- Repository is checked out in the task worktree.",
            "- The current branch reproduces the reported behavior.",
            "",
            "## Repro Steps",
            "",
            f"1. Follow the workflow described by the request: {title}.",
            "2. Observe the current incorrect behavior in the relevant code path.",
            "3. Compare the observed result against the expected result below.",
            "",
            "## Observed Result",
            "",
            f"- {message}",
            "",
            "## Expected Result",
            "",
            "- The reported issue no longer occurs once the fix is applied.",
            "",
            "## Regression Test Target",
            "",
            "- Add or update a regression-oriented test that fails before the fix and passes after it.",
            "",
        ]
    )


def _render_issue_fix_plan(task: dict, title: str, message: str) -> str:
    _ = task
    request_summary = _single_line(message)
    return "\n".join(
        [
            "# Fix Plan",
            "",
            "## Root Cause Hypothesis",
            "",
            f"- The behavior described by the request likely originates in the code path for: {title}.",
            "",
            "## Fix Strategy",
            "",
            f"1. Confirm the failing path described by: {request_summary}.",
            "2. Add or update a regression test around the failing path.",
            "3. Implement the fix and re-run the relevant checks.",
            "4. Update task docs with the verified outcome.",
            "",
            "## Design Evaluation",
            "",
            "- Design Mode: `none`",
            "- Decision Reason: `existing contract only`",
            "- Confidence: `medium`",
            "- Layer Impact: `layer-preserving`",
            "- Layer Decision Reason: `n/a`",
            "- Required Design Artifacts: `none`",
            "",
            "## Design Artifacts",
            "",
            "- Connection Diagram: `n/a`",
            "- Sequence Diagram: `n/a`",
            "- Boundary Note: `n/a`",
            "",
            "## Test Strategy",
            "",
            "### Normal Cases",
            "",
            "- [ ] Regression scenario now passes",
            "",
            "### Edge Cases",
            "",
            "- [ ] Neighboring behavior remains stable",
            "",
            "### Exception Cases",
            "",
            "- [ ] Invalid or missing input still fails safely",
            "",
            "## Verification Mapping",
            "",
            "- `Regression scenario now passes` -> `sisyphus verify`",
            "- `Neighboring behavior remains stable` -> `targeted regression test`",
            "- `Invalid or missing input still fails safely` -> `manual review`",
            "",
            "## External LLM Review",
            "",
            "- Required: `no`",
            "- Provider: `n/a`",
            "- Purpose: `n/a`",
            "- Trigger: `n/a`",
            "",
        ]
    )


def _append_event_log(repo_root: Path, entry: dict) -> None:
    log_path = event_log_file(repo_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _new_event_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"


def _slugify(value: str, *, fallback: str = "conversation-task") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or fallback


def _title_from_message(message: str) -> str:
    line = _single_line(message)
    return line[:72] or "Conversation Task"


def _single_line(value: str) -> str:
    collapsed = " ".join(part.strip() for part in value.splitlines() if part.strip())
    return collapsed or "No details provided"
