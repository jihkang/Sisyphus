from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import json
import re
import subprocess

from .config import SisyphusConfig
from .gitops import (
    GitOperationError,
    commit_staged_changes,
    push_branch,
    remote_url,
    stage_all_changes,
    has_staged_changes,
)
from .metrics import publish_manual_intervention_required, publish_reopened_after_verify
from .promotion_state import (
    PROMOTION_STATUS_COMMITTED,
    PROMOTION_STATUS_MERGED,
    PROMOTION_STATUS_PR_OPEN,
    PROMOTION_STATUS_PUSHED,
    PROMOTION_STATUS_RECORDED,
    PROMOTION_STRATEGY_STACKED,
    ensure_task_promotion_defaults,
)
from .state import list_task_records, load_task_record, save_task_record, utc_now


DEFAULT_CHANGESET_PATH = "CHANGESET.md"
DEFAULT_PROMOTION_RECEIPT_PATH = "artifacts/promotion/merge_receipt.json"
DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH = "artifacts/promotion/open_pr_receipt.json"


@dataclass(slots=True)
class MergeReceiptOutcome:
    task_id: str
    branch: str | None
    pr_number: int
    title: str
    recorded_at: str
    receipt_path: Path
    changeset_path: Path
    close_attempted: bool
    closed: bool
    close_status: str | None
    close_gate_codes: tuple[str, ...]
    child_retargeted_task_ids: tuple[str, ...]


@dataclass(slots=True)
class PromotionExecutionOutcome:
    task_id: str
    branch: str
    base_branch: str
    head_branch: str
    status: str
    commit_sha: str
    pr_number: int | None
    pr_url: str | None
    receipt_path: Path


@dataclass(slots=True)
class PromotionBaseResolution:
    base_branch: str
    source: str
    reason: str
    parent_task_id: str | None
    parent_artifact_id: str | None
    parent_branch: str | None


def execute_promotion(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str,
    remote_name: str = "origin",
    repo_full_name: str | None = None,
    title: str | None = None,
    body: str | None = None,
    commit_message: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    draft: bool = True,
) -> PromotionExecutionOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    ensure_task_promotion_defaults(task)
    promotion = task["promotion"]

    if not bool(promotion.get("required")):
        raise ValueError(f"task `{task_id}` does not require promotion")

    current_status = str(promotion.get("status") or "").strip()
    if current_status in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
        raise ValueError(f"task `{task_id}` is already merged or promotion-recorded")

    worktree_path = Path(str(task.get("worktree_path", "")))
    if not worktree_path.is_dir():
        raise FileNotFoundError(f"task worktree does not exist: {worktree_path}")

    normalized_remote = remote_name.strip()
    if not normalized_remote:
        raise ValueError("remote_name must be non-empty")

    resolved_base_branch = (
        ""
    )
    resolved_head_branch = (
        (head_branch or "").strip()
        or str(promotion.get("head_branch") or "").strip()
        or str(task.get("branch") or "").strip()
    )
    if not resolved_head_branch:
        raise ValueError(f"task `{task_id}` is missing a head branch for promotion")
    base_resolution = resolve_promotion_base(
        repo_root=repo_root,
        config=config,
        task=task,
        explicit_base_branch=base_branch,
    )
    resolved_base_branch = base_resolution.base_branch

    resolved_title = (title or "").strip() or _default_promotion_title(task)
    resolved_body = (body or "").strip() or _default_promotion_body(task, title=resolved_title)
    resolved_commit_message = (commit_message or "").strip() or _default_commit_message(task, title=resolved_title)
    resolved_repo_full_name = (
        (repo_full_name or "").strip()
        or str(promotion.get("repo_full_name") or "").strip()
        or _repo_full_name_from_remote_url(remote_url(worktree_path, normalized_remote))
    )

    task_dir = repo_root / str(task["task_dir"])
    receipt_relative_path = Path(
        str(promotion.get("execution_receipt_path") or DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH)
    )
    receipt_path = task_dir / receipt_relative_path
    task["promotion"]["execution_receipt_path"] = str(receipt_relative_path)
    task["promotion"]["remote_name"] = normalized_remote
    if resolved_repo_full_name:
        task["promotion"]["repo_full_name"] = resolved_repo_full_name
    task["promotion"]["parent_task_id"] = base_resolution.parent_task_id
    task["promotion"]["parent_artifact_id"] = base_resolution.parent_artifact_id
    task["promotion"]["base_branch"] = resolved_base_branch
    task["promotion"]["base_source"] = base_resolution.source
    task["promotion"]["base_reason"] = base_resolution.reason
    task["promotion"]["resolved_parent_branch"] = base_resolution.parent_branch
    task["promotion"]["head_branch"] = resolved_head_branch
    task["promotion"]["title"] = resolved_title

    stage_all_changes(worktree_path)
    staged_changes = has_staged_changes(worktree_path)
    commit_sha = str(task["promotion"].get("head_sha") or "").strip()

    if staged_changes:
        commit_sha = commit_staged_changes(worktree_path, resolved_commit_message)
        task["promotion"]["required"] = True
        task["promotion"]["status"] = PROMOTION_STATUS_COMMITTED
        task["promotion"]["head_sha"] = commit_sha
        task["promotion"]["commit_message"] = resolved_commit_message
        task["promotion"]["committed_at"] = utc_now()
        save_task_record(task_file=task_file, task=task)
        _write_promotion_execution_receipt(
            task=task,
            receipt_path=receipt_path,
            draft=draft,
        )
    elif not commit_sha:
        raise GitOperationError("no staged changes available for promotion")

    push_branch(worktree_path, normalized_remote, resolved_head_branch, set_upstream=True)
    task["promotion"]["status"] = PROMOTION_STATUS_PR_OPEN if _task_has_open_pr(task) else PROMOTION_STATUS_PUSHED
    task["promotion"]["head_sha"] = commit_sha
    task["promotion"]["pushed_at"] = utc_now()
    save_task_record(task_file=task_file, task=task)
    _write_promotion_execution_receipt(
        task=task,
        receipt_path=receipt_path,
        draft=draft,
    )

    if not _task_has_open_pr(task):
        pr_url = _create_pull_request(
            worktree_path=worktree_path,
            repo_full_name=resolved_repo_full_name or None,
            base_branch=resolved_base_branch,
            head_branch=resolved_head_branch,
            title=resolved_title,
            body=resolved_body,
            draft=draft,
        )
        pr_number = _pull_request_number_from_url(pr_url)
        task["promotion"]["status"] = PROMOTION_STATUS_PR_OPEN
        task["promotion"]["pr_url"] = pr_url
        task["promotion"]["pr_number"] = pr_number
        task["promotion"]["pr_opened_at"] = utc_now()
        save_task_record(task_file=task_file, task=task)
        _write_promotion_execution_receipt(
            task=task,
            receipt_path=receipt_path,
            draft=draft,
        )

    return PromotionExecutionOutcome(
        task_id=str(task["id"]),
        branch=str(task.get("branch") or resolved_head_branch),
        base_branch=resolved_base_branch,
        head_branch=resolved_head_branch,
        status=str(task["promotion"]["status"]),
        commit_sha=str(task["promotion"]["head_sha"]),
        pr_number=int(task["promotion"]["pr_number"]) if task["promotion"].get("pr_number") is not None else None,
        pr_url=str(task["promotion"]["pr_url"]) if task["promotion"].get("pr_url") else None,
        receipt_path=receipt_path,
    )


def resolve_promotion_base(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task: dict,
    explicit_base_branch: str | None = None,
) -> PromotionBaseResolution:
    ensure_task_promotion_defaults(task)
    promotion = task["promotion"]

    override_base = (
        (explicit_base_branch or "").strip()
        or str(promotion.get("base_override") or "").strip()
    )
    if override_base:
        return PromotionBaseResolution(
            base_branch=override_base,
            source="explicit_override",
            reason="promotion uses an explicit base override",
            parent_task_id=str(promotion.get("parent_task_id")) if promotion.get("parent_task_id") else None,
            parent_artifact_id=str(promotion.get("parent_artifact_id")) if promotion.get("parent_artifact_id") else None,
            parent_branch=None,
        )

    strategy = str(promotion.get("strategy") or "").strip().lower()
    parent_task_id = str(promotion.get("parent_task_id") or "").strip() or None
    parent_artifact_id = str(promotion.get("parent_artifact_id") or "").strip() or None
    if strategy == PROMOTION_STRATEGY_STACKED and parent_task_id:
        try:
            parent_task, _ = load_task_record(
                repo_root=repo_root,
                task_dir_name=config.task_dir,
                task_id=parent_task_id,
            )
        except FileNotFoundError:
            fallback_base = str(task.get("base_branch") or "").strip()
            if not fallback_base:
                raise ValueError(
                    f"stacked promotion for `{task['id']}` references missing parent task `{parent_task_id}` without a fallback base"
                )
            return PromotionBaseResolution(
                base_branch=fallback_base,
                source="stacked_parent_missing_fallback",
                reason=f"parent task `{parent_task_id}` could not be loaded, so the task base branch is used",
                parent_task_id=parent_task_id,
                parent_artifact_id=parent_artifact_id,
                parent_branch=None,
            )

        ensure_task_promotion_defaults(parent_task)
        parent_promotion = parent_task["promotion"]
        parent_branch = (
            str(parent_promotion.get("head_branch") or "").strip()
            or str(parent_task.get("branch") or "").strip()
            or None
        )
        parent_target = (
            str(parent_promotion.get("base_branch") or "").strip()
            or str(parent_task.get("base_branch") or "").strip()
            or None
        )
        parent_status = str(parent_promotion.get("status") or "").strip()
        if parent_status in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
            if not parent_target:
                raise ValueError(f"parent task `{parent_task_id}` is merged but does not expose a merge target base")
            return PromotionBaseResolution(
                base_branch=parent_target,
                source="parent_merge_target",
                reason=f"stacked promotion uses the merged parent task `{parent_task_id}` merge target",
                parent_task_id=parent_task_id,
                parent_artifact_id=parent_artifact_id,
                parent_branch=parent_branch,
            )
        if parent_branch:
            return PromotionBaseResolution(
                base_branch=parent_branch,
                source="parent_task_branch",
                reason=f"stacked promotion follows the open parent task `{parent_task_id}` branch",
                parent_task_id=parent_task_id,
                parent_artifact_id=parent_artifact_id,
                parent_branch=parent_branch,
            )
        if parent_target:
            return PromotionBaseResolution(
                base_branch=parent_target,
                source="parent_task_base_fallback",
                reason=f"stacked promotion uses the parent task `{parent_task_id}` base branch as fallback",
                parent_task_id=parent_task_id,
                parent_artifact_id=parent_artifact_id,
                parent_branch=None,
            )
        raise ValueError(f"parent task `{parent_task_id}` does not expose a usable branch for stacked promotion")

    resolved_base_branch = (
        str(promotion.get("base_branch") or "").strip()
        or str(task.get("base_branch") or "").strip()
    )
    if not resolved_base_branch:
        raise ValueError(f"task `{task['id']}` is missing a base branch for promotion")
    if strategy == PROMOTION_STRATEGY_STACKED and parent_artifact_id:
        reason = f"stacked promotion falls back to the task base branch because parent artifact `{parent_artifact_id}` is unresolved"
        source = "parent_artifact_fallback"
    else:
        reason = "promotion uses the task base branch"
        source = "task_base_branch"
    return PromotionBaseResolution(
        base_branch=resolved_base_branch,
        source=source,
        reason=reason,
        parent_task_id=parent_task_id,
        parent_artifact_id=parent_artifact_id,
        parent_branch=None,
    )


def mark_stacked_children_for_retarget(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    parent_task: dict,
    triggered_at: str,
) -> tuple[str, ...]:
    ensure_task_promotion_defaults(parent_task)
    parent_promotion = parent_task["promotion"]
    parent_task_id = str(parent_task.get("id") or "").strip()
    if not parent_task_id:
        return ()

    parent_branch = (
        str(parent_promotion.get("head_branch") or "").strip()
        or str(parent_task.get("branch") or "").strip()
        or None
    )
    parent_target = (
        str(parent_promotion.get("base_branch") or "").strip()
        or str(parent_task.get("base_branch") or "").strip()
        or None
    )
    updated: list[str] = []
    for candidate in list_task_records(repo_root=repo_root, task_dir_name=config.task_dir):
        if str(candidate.get("id") or "") == parent_task_id:
            continue
        if str(candidate.get("status") or "").strip() == "closed":
            continue
        ensure_task_promotion_defaults(candidate)
        promotion = candidate["promotion"]
        if str(promotion.get("strategy") or "").strip().lower() != PROMOTION_STRATEGY_STACKED:
            continue
        if str(promotion.get("parent_task_id") or "").strip() != parent_task_id:
            continue
        if str(promotion.get("status") or "").strip() in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
            continue

        child_task, child_task_file = load_task_record(
            repo_root=repo_root,
            task_dir_name=config.task_dir,
            task_id=str(candidate["id"]),
        )
        ensure_task_promotion_defaults(child_task)
        previous_verify_status = str(child_task.get("verify_status") or "").strip()
        child_promotion = child_task["promotion"]
        child_promotion["retarget_required"] = True
        child_promotion["reverify_required"] = True
        child_promotion["retarget_required_at"] = triggered_at
        child_promotion["retarget_parent_task_id"] = parent_task_id
        child_promotion["retarget_parent_branch"] = parent_branch
        child_promotion["retarget_merge_target"] = parent_target
        child_task["verify_status"] = "not_run"
        child_task["status"] = "blocked"
        child_task["stage"] = "promotion"
        child_task["workflow_phase"] = "retarget_required"
        child_task["gates"] = [
            gate
            for gate in child_task.get("gates", [])
            if not (
                isinstance(gate, Mapping)
                and str(gate.get("code", "")).strip() == "PARENT_RETARGET_REQUIRED"
                and str(gate.get("source", "")).strip() == "promotion"
            )
        ]
        child_task["gates"].append(
            {
                "code": "PARENT_RETARGET_REQUIRED",
                "message": f"parent task `{parent_task_id}` merged; retarget the stacked child branch and rerun verify",
                "blocking": True,
                "source": "promotion",
                "created_at": utc_now(),
            }
        )
        save_task_record(task_file=child_task_file, task=child_task)
        publish_manual_intervention_required(
            repo_root,
            config,
            task_id=str(child_task["id"]),
            reason="parent_retarget_required",
            workflow_phase="retarget_required",
            status=str(child_task.get("status") or ""),
            detail="parent promotion merged and the stacked child now requires retarget and reverify",
        )
        if previous_verify_status == "passed":
            publish_reopened_after_verify(
                repo_root,
                config,
                task_id=str(child_task["id"]),
                reason="stacked_parent_merged",
                workflow_phase="retarget_required",
                previous_verify_status=previous_verify_status,
            )
        updated.append(str(child_task["id"]))
    return tuple(updated)


def record_merged_pull_request(
    repo_root: Path,
    config: SisyphusConfig,
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
) -> MergeReceiptOutcome:
    if pr_number < 1:
        raise ValueError("pr_number must be a positive integer")

    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("title must be non-empty")

    task, task_file = _resolve_task(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        branch=branch,
        head_branch=head_branch,
    )
    recorded_at = utc_now()
    normalized_changed_files = _normalize_changed_files(changed_files)
    total_additions = _resolve_total_count(additions, normalized_changed_files, "additions")
    total_deletions = _resolve_total_count(deletions, normalized_changed_files, "deletions")

    task_dir = repo_root / str(task["task_dir"])
    docs = dict(task.get("docs", {}))
    receipt_relative_path = Path(str(docs.get("promotion") or DEFAULT_PROMOTION_RECEIPT_PATH))
    changeset_relative_path = Path(str(docs.get("changeset") or DEFAULT_CHANGESET_PATH))
    receipt_path = task_dir / receipt_relative_path
    changeset_path = task_dir / changeset_relative_path

    receipt = {
        "recorded_at": recorded_at,
        "task_id": task["id"],
        "task_branch": task.get("branch"),
        "base_branch": base_branch or task.get("base_branch"),
        "repo_full_name": repo_full_name,
        "pull_request": {
            "number": pr_number,
            "title": normalized_title,
            "url": url,
            "head_branch": head_branch or branch or task.get("branch"),
            "head_sha": head_sha,
            "merge_commit_sha": merge_commit_sha,
            "merged_at": merged_at,
            "merged_by": merged_by,
            "merge_method": merge_method,
        },
        "base_resolution": {
            "strategy": task["promotion"].get("strategy"),
            "source": task["promotion"].get("base_source"),
            "reason": task["promotion"].get("base_reason"),
            "parent_task_id": task["promotion"].get("parent_task_id"),
            "parent_artifact_id": task["promotion"].get("parent_artifact_id"),
            "parent_branch": task["promotion"].get("resolved_parent_branch"),
        },
        "changes": {
            "file_count": len(normalized_changed_files),
            "additions": total_additions,
            "deletions": total_deletions,
            "files": normalized_changed_files,
        },
    }

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    changeset_path.parent.mkdir(parents=True, exist_ok=True)
    changeset_path.write_text(_render_changeset_markdown(receipt), encoding="utf-8")

    ensure_task_promotion_defaults(task)
    task["promotion"].update(
        {
            "required": True,
            "status": PROMOTION_STATUS_RECORDED,
            "repo_full_name": repo_full_name,
            "recorded_at": recorded_at,
            "pr_number": pr_number,
            "title": normalized_title,
            "pr_url": url,
            "head_branch": head_branch or branch or task.get("branch"),
            "base_branch": base_branch or task.get("base_branch"),
            "head_sha": head_sha,
            "merge_commit_sha": merge_commit_sha,
            "merged_at": merged_at,
            "merged_by": merged_by,
            "merge_method": merge_method,
            "receipt_path": str(receipt_relative_path),
            "changeset_path": str(changeset_relative_path),
        }
    )
    save_task_record(task_file=task_file, task=task)
    close_attempted = False
    closed = False
    close_status: str | None = None
    close_gate_codes: tuple[str, ...] = ()
    if str(task.get("verify_status") or "").strip() == "passed" and str(task.get("status") or "").strip() != "closed":
        from .closeout import run_close

        close_attempted = True
        close_outcome = run_close(repo_root=repo_root, config=config, task_id=str(task["id"]), allow_dirty=True)
        closed = close_outcome.closed
        close_status = close_outcome.status
        close_gate_codes = tuple(
            str(gate.get("code"))
            for gate in close_outcome.gates
            if isinstance(gate, Mapping) and str(gate.get("code", "")).strip()
        )
    child_retargeted_task_ids = mark_stacked_children_for_retarget(
        repo_root=repo_root,
        config=config,
        parent_task=task,
        triggered_at=recorded_at,
    )

    return MergeReceiptOutcome(
        task_id=str(task["id"]),
        branch=str(task.get("branch")) if task.get("branch") else None,
        pr_number=pr_number,
        title=normalized_title,
        recorded_at=recorded_at,
        receipt_path=receipt_path,
        changeset_path=changeset_path,
        close_attempted=close_attempted,
        closed=closed,
        close_status=close_status,
        close_gate_codes=close_gate_codes,
        child_retargeted_task_ids=child_retargeted_task_ids,
    )


def _resolve_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str | None,
    branch: str | None,
    head_branch: str | None,
) -> tuple[dict, Path]:
    if task_id:
        task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
        expected_branch = (branch or head_branch or "").strip()
        if expected_branch and str(task.get("branch") or "") != expected_branch:
            raise ValueError(f"task `{task_id}` does not match branch `{expected_branch}`")
        return task, task_file

    branch_name = (branch or head_branch or "").strip()
    if not branch_name:
        raise ValueError("merged pull request requires task_id or branch/head_branch")

    for candidate in list_task_records(repo_root=repo_root, task_dir_name=config.task_dir):
        if str(candidate.get("branch") or "") != branch_name:
            continue
        return load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=str(candidate["id"]))

    raise FileNotFoundError(f"no task found for branch `{branch_name}`")


def _normalize_changed_files(changed_files: list[dict[str, object]] | None) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_item in changed_files or []:
        if not isinstance(raw_item, Mapping):
            raise TypeError("changed_files entries must be mapping objects")
        path = str(raw_item.get("path", "")).strip()
        if not path:
            raise ValueError("changed_files entries require a non-empty `path`")
        item: dict[str, object] = {"path": path}
        status = str(raw_item.get("status", "modified")).strip() or "modified"
        item["status"] = status
        previous_path = str(raw_item.get("previous_path", "")).strip()
        if previous_path:
            item["previous_path"] = previous_path
        additions = _coerce_optional_int(raw_item.get("additions"))
        deletions = _coerce_optional_int(raw_item.get("deletions"))
        if additions is not None:
            item["additions"] = additions
        if deletions is not None:
            item["deletions"] = deletions
        normalized.append(item)
    return normalized


def _coerce_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _resolve_total_count(
    explicit_value: int | None,
    changed_files: list[dict[str, object]],
    key: str,
) -> int | None:
    if explicit_value is not None:
        return explicit_value
    values = [int(item[key]) for item in changed_files if isinstance(item.get(key), int)]
    if not values:
        return None
    return sum(values)


def _render_changeset_markdown(receipt: Mapping[str, object]) -> str:
    pull_request = dict(receipt.get("pull_request", {})) if isinstance(receipt.get("pull_request"), Mapping) else {}
    changes = dict(receipt.get("changes", {})) if isinstance(receipt.get("changes"), Mapping) else {}
    files = list(changes.get("files", [])) if isinstance(changes.get("files"), list) else []
    pr_number = pull_request.get("number")
    title = str(pull_request.get("title", "")).strip()
    url = str(pull_request.get("url", "")).strip()
    repo_full_name = str(receipt.get("repo_full_name", "")).strip()
    task_id = str(receipt.get("task_id", "")).strip()
    task_branch = str(receipt.get("task_branch", "")).strip()
    base_branch = str(receipt.get("base_branch", "")).strip()
    head_branch = str(pull_request.get("head_branch", "")).strip()
    merge_commit_sha = str(pull_request.get("merge_commit_sha", "")).strip()
    merged_at = str(pull_request.get("merged_at", "")).strip()
    merge_method = str(pull_request.get("merge_method", "")).strip()
    merged_by = str(pull_request.get("merged_by", "")).strip()
    file_count = changes.get("file_count")
    additions = changes.get("additions")
    deletions = changes.get("deletions")

    lines = [
        "# Changeset",
        "",
        "## Merge",
        "",
        f"- Task: `{task_id}`",
    ]
    if pr_number is not None:
        if url:
            lines.append(f"- Pull Request: [#{pr_number}]({url})")
        else:
            lines.append(f"- Pull Request: `#{pr_number}`")
    if title:
        lines.append(f"- Title: {title}")
    if repo_full_name:
        lines.append(f"- Repository: `{repo_full_name}`")
    if task_branch:
        lines.append(f"- Task Branch: `{task_branch}`")
    if head_branch or base_branch:
        lines.append(f"- Merge Target: `{head_branch or task_branch}` -> `{base_branch}`")
    if merge_commit_sha:
        lines.append(f"- Merge Commit: `{merge_commit_sha}`")
    if merge_method:
        lines.append(f"- Merge Method: `{merge_method}`")
    if merged_by:
        lines.append(f"- Merged By: `{merged_by}`")
    if merged_at:
        lines.append(f"- Merged At: `{merged_at}`")
    if file_count is not None or additions is not None or deletions is not None:
        summary_bits: list[str] = []
        if file_count is not None:
            summary_bits.append(f"{file_count} files")
        if additions is not None:
            summary_bits.append(f"+{additions}")
        if deletions is not None:
            summary_bits.append(f"-{deletions}")
        lines.append(f"- Diff Summary: {', '.join(summary_bits)}")

    lines.extend(["", "## Changed Paths", ""])
    if files:
        for raw_item in files:
            if not isinstance(raw_item, Mapping):
                continue
            path = str(raw_item.get("path", "")).strip()
            status = str(raw_item.get("status", "modified")).strip() or "modified"
            previous_path = str(raw_item.get("previous_path", "")).strip()
            additions = raw_item.get("additions")
            deletions = raw_item.get("deletions")
            details: list[str] = [status]
            if previous_path:
                details.append(f"from {previous_path}")
            if additions is not None or deletions is not None:
                change_bits: list[str] = []
                if additions is not None:
                    change_bits.append(f"+{additions}")
                if deletions is not None:
                    change_bits.append(f"-{deletions}")
                details.append(", ".join(change_bits))
            lines.append(f"- `{path}` ({'; '.join(details)})")
    else:
        lines.append("- No changed file details were provided.")

    top_level_counts = _top_level_path_counts(files)
    if top_level_counts:
        lines.extend(["", "## Scope", ""])
        for root, count in sorted(top_level_counts.items()):
            lines.append(f"- `{root}`: {count} files")

    lines.append("")
    return "\n".join(lines)


def _top_level_path_counts(files: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_item in files:
        if not isinstance(raw_item, Mapping):
            continue
        path = str(raw_item.get("path", "")).strip()
        if not path:
            continue
        root = path.split("/", 1)[0]
        if "." in root and "/" not in path:
            root = "(repo root files)"
        counts[root] = counts.get(root, 0) + 1
    return counts


def _task_has_open_pr(task: dict) -> bool:
    promotion = task.get("promotion", {})
    if not isinstance(promotion, dict):
        return False
    pr_number = promotion.get("pr_number")
    pr_url = str(promotion.get("pr_url") or "").strip()
    return pr_number not in (None, "") and bool(pr_url)


def _default_promotion_title(task: Mapping[str, object]) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "task").strip().replace("-", " ")
    if task_id:
        return f"{task_id}: {slug}"
    return slug or "Sisyphus promotion"


def _default_commit_message(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    if task_id:
        return f"{task_id}: {title}"
    return title


def _default_promotion_body(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "").strip()
    verify_status = str(task.get("verify_status") or "not_run").strip() or "not_run"
    lines = [
        "## Summary",
        "",
        f"- Promote task `{task_id}`",
    ]
    if slug:
        lines.append(f"- Slug: `{slug}`")
    lines.extend(
        [
            f"- Verify status: `{verify_status}`",
            "",
            "## Notes",
            "",
            f"- Title: {title}",
            "- Generated by Sisyphus promotion executor",
            "",
        ]
    )
    return "\n".join(lines)


def _create_pull_request(
    *,
    worktree_path: Path,
    repo_full_name: str | None,
    base_branch: str,
    head_branch: str,
    title: str,
    body: str,
    draft: bool,
) -> str:
    args = [
        "pr",
        "create",
        "--base",
        base_branch,
        "--head",
        head_branch,
        "--title",
        title,
        "--body",
        body,
    ]
    if draft:
        args.append("--draft")
    if repo_full_name:
        args.extend(["--repo", repo_full_name])

    completed = _run_gh(worktree_path, args, error_prefix="failed to create pull request")
    pr_url = _extract_pull_request_url(completed.stdout) or _extract_pull_request_url(completed.stderr)
    if not pr_url:
        raise GitOperationError("failed to create pull request: gh did not return a pull request URL")
    return pr_url


def _write_promotion_execution_receipt(*, task: dict, receipt_path: Path, draft: bool) -> None:
    promotion = dict(task.get("promotion", {})) if isinstance(task.get("promotion"), dict) else {}
    payload = {
        "written_at": utc_now(),
        "task_id": task.get("id"),
        "task_branch": task.get("branch"),
        "status": promotion.get("status"),
        "repo_full_name": promotion.get("repo_full_name"),
        "remote_name": promotion.get("remote_name"),
        "base_branch": promotion.get("base_branch"),
        "base_resolution": {
            "strategy": promotion.get("strategy"),
            "source": promotion.get("base_source"),
            "reason": promotion.get("base_reason"),
            "parent_task_id": promotion.get("parent_task_id"),
            "parent_artifact_id": promotion.get("parent_artifact_id"),
            "parent_branch": promotion.get("resolved_parent_branch"),
        },
        "head_branch": promotion.get("head_branch"),
        "commit": {
            "message": promotion.get("commit_message"),
            "sha": promotion.get("head_sha"),
            "committed_at": promotion.get("committed_at"),
        },
        "push": {
            "pushed_at": promotion.get("pushed_at"),
        },
        "pull_request": {
            "number": promotion.get("pr_number"),
            "url": promotion.get("pr_url"),
            "title": promotion.get("title"),
            "opened_at": promotion.get("pr_opened_at"),
            "draft": draft,
        },
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_gh(repo_root: Path, args: list[str], *, error_prefix: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["gh", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed

    message = (completed.stderr or completed.stdout or "").strip()
    if not message:
        message = "gh command failed"
    raise GitOperationError(f"{error_prefix}: {message}")


def _extract_pull_request_url(output: str | None) -> str | None:
    if not output:
        return None
    match = re.search(r"https://github\.com/\S+/pull/\d+", output)
    if not match:
        return None
    return match.group(0)


def _pull_request_number_from_url(pr_url: str | None) -> int | None:
    if not pr_url:
        return None
    match = re.search(r"/pull/(\d+)(?:$|[?#])", pr_url)
    if not match:
        return None
    return int(match.group(1))


def _repo_full_name_from_remote_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.startswith("git@github.com:"):
        repo = normalized.split(":", 1)[1]
    elif "github.com/" in normalized:
        repo = normalized.split("github.com/", 1)[1]
    else:
        return None
    repo = repo.strip().rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo or None
