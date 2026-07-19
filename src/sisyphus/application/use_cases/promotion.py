from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

from ...domain.lifecycle import LifecycleAction
from ...domain.promotion import (
    PROMOTION_STATUS_COMMITTED,
    PROMOTION_STATUS_MERGED,
    PROMOTION_STATUS_PR_OPEN,
    PROMOTION_STATUS_PUSHED,
    PROMOTION_STATUS_RECORDED,
    PROMOTION_STRATEGY_STACKED,
    PromotionBaseResolution,
    ensure_task_promotion_defaults,
)
from ...domain.task.models import DEFAULT_CHANGESET_PATH, DEFAULT_PROMOTION_RECEIPT_PATH
from ..commands.promotion import ExecutePromotionCommand, RecordMergedPullRequestCommand
from ..ports.artifacts import ArtifactStorePort
from ..ports.clock import ClockPort
from ..ports.promotion import (
    PromotionTaskPort,
    PullRequestPort,
    PullRequestSpec,
    ReopenedTaskPort,
    VersionControlPort,
)
from ..ports.verification import VerificationConformancePort
from ..ports.workflow import CloseoutPort, ManualInterventionPort, TaskRecord
from ..promotion_records import blocked_phase, blocked_stage, record_promotion_lifecycle_transition
from ..results.artifacts import ArtifactRef
from ..results.promotion import MergeReceiptResult, PromotionExecutionResult


DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH = "artifacts/promotion/open_pr_receipt.json"


class PromotionExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class PromotionService:
    tasks: PromotionTaskPort
    version_control: VersionControlPort
    pull_requests: PullRequestPort
    artifacts: ArtifactStorePort
    conformance: VerificationConformancePort
    closeout: CloseoutPort
    interventions: ManualInterventionPort
    reopened_tasks: ReopenedTaskPort
    clock: ClockPort

    def execute(self, command: ExecutePromotionCommand) -> PromotionExecutionResult:
        task = self.tasks.load(command.task_id)
        ensure_task_promotion_defaults(task)
        promotion = task["promotion"]
        if not bool(promotion.get("required")):
            raise ValueError(f"task `{command.task_id}` does not require promotion")

        transition = record_promotion_lifecycle_transition(
            task,
            LifecycleAction.EXECUTE_PROMOTION,
            self.conformance.snapshot(task),
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = blocked_stage(transition)
            task["workflow_phase"] = blocked_phase(transition)
            self.tasks.save(task)
            codes = ", ".join(transition.blocking_codes) or "lifecycle gate"
            raise ValueError(f"promotion blocked by lifecycle gates: {codes}")

        current_status = str(promotion.get("status") or "").strip()
        if current_status in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
            raise ValueError(f"task `{command.task_id}` is already merged or promotion-recorded")

        workspace = str(task.get("worktree_path") or "")
        if not self.version_control.workspace_exists(workspace):
            raise FileNotFoundError(f"task worktree does not exist: {workspace}")
        remote = command.remote_name.strip()
        if not remote:
            raise ValueError("remote_name must be non-empty")
        head_branch = (
            str(command.head_branch or "").strip()
            or str(promotion.get("head_branch") or "").strip()
            or str(task.get("branch") or "").strip()
        )
        if not head_branch:
            raise ValueError(f"task `{command.task_id}` is missing a head branch for promotion")

        base = self.resolve_base(task, explicit_base_branch=command.base_branch)
        title = str(command.title or "").strip() or _default_promotion_title(task)
        body = str(command.body or "").strip() or _default_promotion_body(task, title=title)
        commit_message = (
            str(command.commit_message or "").strip()
            or _default_commit_message(task, title=title)
        )
        repo_full_name = (
            str(command.repo_full_name or "").strip()
            or str(promotion.get("repo_full_name") or "").strip()
            or str(_repo_full_name_from_remote_url(self.version_control.remote_url(workspace, remote)) or "")
        )
        receipt_path = str(
            promotion.get("execution_receipt_path")
            or DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH
        )
        promotion.update(
            {
                "execution_receipt_path": receipt_path,
                "remote_name": remote,
                "parent_task_id": base.parent_task_id,
                "parent_artifact_id": base.parent_artifact_id,
                "base_branch": base.base_branch,
                "base_source": base.source,
                "base_reason": base.reason,
                "resolved_parent_branch": base.parent_branch,
                "head_branch": head_branch,
                "title": title,
            }
        )
        if repo_full_name:
            promotion["repo_full_name"] = repo_full_name

        self.version_control.stage_all(workspace)
        staged_changes = self.version_control.has_staged_changes(workspace)
        commit_sha = str(promotion.get("head_sha") or "").strip()
        if staged_changes:
            commit_sha = self.version_control.commit(workspace, commit_message)
            promotion.update(
                {
                    "required": True,
                    "status": PROMOTION_STATUS_COMMITTED,
                    "head_sha": commit_sha,
                    "commit_message": commit_message,
                    "committed_at": self.clock.now(),
                }
            )
            self.tasks.save(task)
            self._write_execution_receipt(task, receipt_path, draft=command.draft)
        elif not commit_sha:
            raise PromotionExecutionError("no staged changes available for promotion")

        self.version_control.push(workspace, remote, head_branch)
        promotion["status"] = (
            PROMOTION_STATUS_PR_OPEN if _task_has_open_pr(task) else PROMOTION_STATUS_PUSHED
        )
        promotion["head_sha"] = commit_sha
        promotion["pushed_at"] = self.clock.now()
        self.tasks.save(task)
        self._write_execution_receipt(task, receipt_path, draft=command.draft)

        if not _task_has_open_pr(task):
            pr_url = self.pull_requests.create(
                PullRequestSpec(
                    workspace=workspace,
                    repo_full_name=repo_full_name or None,
                    base_branch=base.base_branch,
                    head_branch=head_branch,
                    title=title,
                    body=body,
                    draft=command.draft,
                )
            )
            promotion["status"] = PROMOTION_STATUS_PR_OPEN
            promotion["pr_url"] = pr_url
            promotion["pr_number"] = _pull_request_number_from_url(pr_url)
            promotion["pr_opened_at"] = self.clock.now()
            self.tasks.save(task)
            self._write_execution_receipt(task, receipt_path, draft=command.draft)

        return PromotionExecutionResult(
            task_id=str(task["id"]),
            branch=str(task.get("branch") or head_branch),
            base_branch=base.base_branch,
            head_branch=head_branch,
            status=str(promotion["status"]),
            commit_sha=str(promotion["head_sha"]),
            pr_number=(int(promotion["pr_number"]) if promotion.get("pr_number") is not None else None),
            pr_url=(str(promotion["pr_url"]) if promotion.get("pr_url") else None),
            receipt=ArtifactRef(relative_path=receipt_path),
        )

    def resolve_base(
        self,
        task: TaskRecord,
        *,
        explicit_base_branch: str | None = None,
    ) -> PromotionBaseResolution:
        ensure_task_promotion_defaults(task)
        promotion = task["promotion"]
        override = (
            str(explicit_base_branch or "").strip()
            or str(promotion.get("base_override") or "").strip()
        )
        if override:
            return PromotionBaseResolution(
                base_branch=override,
                source="explicit_override",
                reason="promotion uses an explicit base override",
                parent_task_id=_optional_text(promotion.get("parent_task_id")),
                parent_artifact_id=_optional_text(promotion.get("parent_artifact_id")),
                parent_branch=None,
            )

        strategy = str(promotion.get("strategy") or "").strip().lower()
        parent_task_id = _optional_text(promotion.get("parent_task_id"))
        parent_artifact_id = _optional_text(promotion.get("parent_artifact_id"))
        if strategy == PROMOTION_STRATEGY_STACKED and parent_task_id:
            try:
                parent = self.tasks.load(parent_task_id)
            except FileNotFoundError:
                fallback = str(task.get("base_branch") or "").strip()
                if not fallback:
                    raise ValueError(
                        f"stacked promotion for `{task['id']}` references missing parent task "
                        f"`{parent_task_id}` without a fallback base"
                    )
                return PromotionBaseResolution(
                    base_branch=fallback,
                    source="stacked_parent_missing_fallback",
                    reason=(
                        f"parent task `{parent_task_id}` could not be loaded, so the task base "
                        "branch is used"
                    ),
                    parent_task_id=parent_task_id,
                    parent_artifact_id=parent_artifact_id,
                    parent_branch=None,
                )
            ensure_task_promotion_defaults(parent)
            parent_promotion = parent["promotion"]
            parent_branch = (
                str(parent_promotion.get("head_branch") or "").strip()
                or str(parent.get("branch") or "").strip()
                or None
            )
            parent_target = (
                str(parent_promotion.get("base_branch") or "").strip()
                or str(parent.get("base_branch") or "").strip()
                or None
            )
            parent_status = str(parent_promotion.get("status") or "").strip()
            if parent_status in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
                if not parent_target:
                    raise ValueError(
                        f"parent task `{parent_task_id}` is merged but does not expose a merge target base"
                    )
                return PromotionBaseResolution(
                    base_branch=parent_target,
                    source="parent_merge_target",
                    reason=(
                        f"stacked promotion uses the merged parent task `{parent_task_id}` merge target"
                    ),
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
                    reason=(
                        f"stacked promotion uses the parent task `{parent_task_id}` base branch as fallback"
                    ),
                    parent_task_id=parent_task_id,
                    parent_artifact_id=parent_artifact_id,
                    parent_branch=None,
                )
            raise ValueError(
                f"parent task `{parent_task_id}` does not expose a usable branch for stacked promotion"
            )

        base_branch = (
            str(promotion.get("base_branch") or "").strip()
            or str(task.get("base_branch") or "").strip()
        )
        if not base_branch:
            raise ValueError(f"task `{task['id']}` is missing a base branch for promotion")
        if strategy == PROMOTION_STRATEGY_STACKED and parent_artifact_id:
            source = "parent_artifact_fallback"
            reason = (
                "stacked promotion falls back to the task base branch because parent artifact "
                f"`{parent_artifact_id}` is unresolved"
            )
        else:
            source = "task_base_branch"
            reason = "promotion uses the task base branch"
        return PromotionBaseResolution(
            base_branch=base_branch,
            source=source,
            reason=reason,
            parent_task_id=parent_task_id,
            parent_artifact_id=parent_artifact_id,
            parent_branch=None,
        )

    def record_merged(self, command: RecordMergedPullRequestCommand) -> MergeReceiptResult:
        if command.pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        title = command.title.strip()
        if not title:
            raise ValueError("title must be non-empty")
        task = self._resolve_task(command)
        transition = record_promotion_lifecycle_transition(
            task,
            LifecycleAction.RECORD_MERGED_PR,
            self.conformance.snapshot(task),
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            self.tasks.save(task)
            codes = ", ".join(transition.blocking_codes) or "lifecycle gate"
            raise ValueError(f"merged pull request recording blocked by lifecycle gates: {codes}")

        recorded_at = self.clock.now()
        changed_files = _normalize_changed_files(command.changed_files)
        additions = _resolve_total_count(command.additions, changed_files, "additions")
        deletions = _resolve_total_count(command.deletions, changed_files, "deletions")
        docs = dict(task.get("docs", {}))
        receipt_path = str(docs.get("promotion") or DEFAULT_PROMOTION_RECEIPT_PATH)
        changeset_path = str(docs.get("changeset") or DEFAULT_CHANGESET_PATH)
        receipt = _merge_receipt_payload(
            task,
            command,
            title=title,
            recorded_at=recorded_at,
            changed_files=changed_files,
            additions=additions,
            deletions=deletions,
        )
        receipt_ref = self.artifacts.write_json(str(task["id"]), receipt_path, receipt)
        changeset_ref = self.artifacts.write_text(
            str(task["id"]),
            changeset_path,
            _render_changeset_markdown(receipt),
        )
        ensure_task_promotion_defaults(task)
        task["promotion"].update(
            {
                "required": True,
                "status": PROMOTION_STATUS_RECORDED,
                "repo_full_name": command.repo_full_name,
                "recorded_at": recorded_at,
                "pr_number": command.pr_number,
                "title": title,
                "pr_url": command.url,
                "head_branch": command.head_branch or command.branch or task.get("branch"),
                "base_branch": command.base_branch or task.get("base_branch"),
                "head_sha": command.head_sha,
                "merge_commit_sha": command.merge_commit_sha,
                "merged_at": command.merged_at,
                "merged_by": command.merged_by,
                "merge_method": command.merge_method,
                "receipt_path": receipt_path,
                "changeset_path": changeset_path,
            }
        )
        self.tasks.save(task)

        close_attempted = False
        closed = False
        close_status: str | None = None
        close_gate_codes: tuple[str, ...] = ()
        if str(task.get("verify_status") or "").strip() == "passed" and str(
            task.get("status") or ""
        ).strip() != "closed":
            close_attempted = True
            close_result = self.closeout.close(str(task["id"]), allow_dirty=True)
            closed = close_result.closed
            close_status = close_result.status
            close_gate_codes = tuple(
                str(gate.get("code"))
                for gate in close_result.gates
                if str(gate.get("code", "")).strip()
            )
        children = self.mark_stacked_children_for_retarget(task, triggered_at=recorded_at)
        return MergeReceiptResult(
            task_id=str(task["id"]),
            branch=_optional_text(task.get("branch")),
            pr_number=command.pr_number,
            title=title,
            recorded_at=recorded_at,
            receipt=receipt_ref,
            changeset=changeset_ref,
            close_attempted=close_attempted,
            closed=closed,
            close_status=close_status,
            close_gate_codes=close_gate_codes,
            child_retargeted_task_ids=children,
        )

    def mark_stacked_children_for_retarget(
        self,
        parent_task: TaskRecord,
        *,
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
        for candidate in self.tasks.list():
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
            if str(promotion.get("status") or "").strip() in {
                PROMOTION_STATUS_MERGED,
                PROMOTION_STATUS_RECORDED,
            }:
                continue
            child = self.tasks.load(str(candidate["id"]))
            ensure_task_promotion_defaults(child)
            previous_verify_status = str(child.get("verify_status") or "").strip()
            child_promotion = child["promotion"]
            child_promotion.update(
                {
                    "retarget_required": True,
                    "reverify_required": True,
                    "retarget_required_at": triggered_at,
                    "retarget_parent_task_id": parent_task_id,
                    "retarget_parent_branch": parent_branch,
                    "retarget_merge_target": parent_target,
                }
            )
            child["verify_status"] = "not_run"
            child["status"] = "blocked"
            child["stage"] = "promotion"
            child["workflow_phase"] = "retarget_required"
            child["gates"] = [
                gate
                for gate in child.get("gates", [])
                if not (
                    isinstance(gate, Mapping)
                    and str(gate.get("code", "")).strip() == "PARENT_RETARGET_REQUIRED"
                    and str(gate.get("source", "")).strip() == "promotion"
                )
            ]
            child["gates"].append(
                {
                    "code": "PARENT_RETARGET_REQUIRED",
                    "message": (
                        f"parent task `{parent_task_id}` merged; retarget the stacked child branch "
                        "and rerun verify"
                    ),
                    "blocking": True,
                    "source": "promotion",
                    "created_at": self.clock.now(),
                }
            )
            self.tasks.save(child)
            self.interventions.required(
                task_id=str(child["id"]),
                reason="parent_retarget_required",
                workflow_phase="retarget_required",
                status=str(child.get("status") or ""),
                detail=(
                    "parent promotion merged and the stacked child now requires retarget and reverify"
                ),
            )
            if previous_verify_status == "passed":
                self.reopened_tasks.publish(
                    task_id=str(child["id"]),
                    reason="stacked_parent_merged",
                    workflow_phase="retarget_required",
                    previous_verify_status=previous_verify_status,
                )
            updated.append(str(child["id"]))
        return tuple(updated)

    def _resolve_task(self, command: RecordMergedPullRequestCommand) -> TaskRecord:
        if command.task_id:
            task = self.tasks.load(command.task_id)
            expected_branch = str(command.branch or command.head_branch or "").strip()
            if expected_branch and str(task.get("branch") or "") != expected_branch:
                raise ValueError(
                    f"task `{command.task_id}` does not match branch `{expected_branch}`"
                )
            return task
        branch = str(command.branch or command.head_branch or "").strip()
        if not branch:
            raise ValueError("merged pull request requires task_id or branch/head_branch")
        for candidate in self.tasks.list():
            if str(candidate.get("branch") or "") == branch:
                return self.tasks.load(str(candidate["id"]))
        raise FileNotFoundError(f"no task found for branch `{branch}`")

    def _write_execution_receipt(self, task: TaskRecord, path: str, *, draft: bool) -> None:
        self.artifacts.write_json(
            str(task["id"]),
            path,
            _execution_receipt_payload(task, draft=draft, written_at=self.clock.now()),
        )


def _execution_receipt_payload(
    task: TaskRecord,
    *,
    draft: bool,
    written_at: str,
) -> dict[str, object]:
    promotion = dict(task.get("promotion", {}))
    return {
        "written_at": written_at,
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
        "push": {"pushed_at": promotion.get("pushed_at")},
        "pull_request": {
            "number": promotion.get("pr_number"),
            "url": promotion.get("pr_url"),
            "title": promotion.get("title"),
            "opened_at": promotion.get("pr_opened_at"),
            "draft": draft,
        },
    }


def _merge_receipt_payload(
    task: TaskRecord,
    command: RecordMergedPullRequestCommand,
    *,
    title: str,
    recorded_at: str,
    changed_files: list[dict[str, object]],
    additions: int | None,
    deletions: int | None,
) -> dict[str, object]:
    promotion = task["promotion"]
    return {
        "recorded_at": recorded_at,
        "task_id": task["id"],
        "task_branch": task.get("branch"),
        "base_branch": command.base_branch or task.get("base_branch"),
        "repo_full_name": command.repo_full_name,
        "pull_request": {
            "number": command.pr_number,
            "title": title,
            "url": command.url,
            "head_branch": command.head_branch or command.branch or task.get("branch"),
            "head_sha": command.head_sha,
            "merge_commit_sha": command.merge_commit_sha,
            "merged_at": command.merged_at,
            "merged_by": command.merged_by,
            "merge_method": command.merge_method,
        },
        "base_resolution": {
            "strategy": promotion.get("strategy"),
            "source": promotion.get("base_source"),
            "reason": promotion.get("base_reason"),
            "parent_task_id": promotion.get("parent_task_id"),
            "parent_artifact_id": promotion.get("parent_artifact_id"),
            "parent_branch": promotion.get("resolved_parent_branch"),
        },
        "changes": {
            "file_count": len(changed_files),
            "additions": additions,
            "deletions": deletions,
            "files": changed_files,
        },
    }


def _normalize_changed_files(changed_files: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_item in changed_files:
        if not isinstance(raw_item, Mapping):
            raise TypeError("changed_files entries must be mapping objects")
        path = str(raw_item.get("path", "")).strip()
        if not path:
            raise ValueError("changed_files entries require a non-empty `path`")
        item: dict[str, object] = {
            "path": path,
            "status": str(raw_item.get("status", "modified")).strip() or "modified",
        }
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
    return None if value in (None, "") else int(value)


def _resolve_total_count(
    explicit_value: int | None,
    changed_files: list[dict[str, object]],
    key: str,
) -> int | None:
    if explicit_value is not None:
        return explicit_value
    values = [int(item[key]) for item in changed_files if isinstance(item.get(key), int)]
    return sum(values) if values else None


def _render_changeset_markdown(receipt: Mapping[str, object]) -> str:
    pull_request = dict(receipt.get("pull_request", {}))
    changes = dict(receipt.get("changes", {}))
    files = list(changes.get("files", []))
    lines = ["# Changeset", "", "## Merge", "", f"- Task: `{receipt.get('task_id', '')}`"]
    pr_number = pull_request.get("number")
    url = str(pull_request.get("url") or "")
    if pr_number is not None:
        lines.append(f"- Pull Request: [#{pr_number}]({url})" if url else f"- Pull Request: `#{pr_number}`")
    fields = [
        ("Title", pull_request.get("title")),
        ("Repository", receipt.get("repo_full_name")),
        ("Task Branch", receipt.get("task_branch")),
    ]
    for label, value in fields:
        if value:
            rendered = str(value)
            lines.append(f"- {label}: {rendered}" if label == "Title" else f"- {label}: `{rendered}`")
    head = str(pull_request.get("head_branch") or receipt.get("task_branch") or "")
    base = str(receipt.get("base_branch") or "")
    if head or base:
        lines.append(f"- Merge Target: `{head}` -> `{base}`")
    for label, key in [
        ("Merge Commit", "merge_commit_sha"),
        ("Merge Method", "merge_method"),
        ("Merged By", "merged_by"),
        ("Merged At", "merged_at"),
    ]:
        if pull_request.get(key):
            lines.append(f"- {label}: `{pull_request[key]}`")
    summary: list[str] = []
    if changes.get("file_count") is not None:
        summary.append(f"{changes['file_count']} files")
    if changes.get("additions") is not None:
        summary.append(f"+{changes['additions']}")
    if changes.get("deletions") is not None:
        summary.append(f"-{changes['deletions']}")
    if summary:
        lines.append(f"- Diff Summary: {', '.join(summary)}")
    lines.extend(["", "## Changed Paths", ""])
    if files:
        for raw_item in files:
            if not isinstance(raw_item, Mapping):
                continue
            details = [str(raw_item.get("status") or "modified")]
            if raw_item.get("previous_path"):
                details.append(f"from {raw_item['previous_path']}")
            counts: list[str] = []
            if raw_item.get("additions") is not None:
                counts.append(f"+{raw_item['additions']}")
            if raw_item.get("deletions") is not None:
                counts.append(f"-{raw_item['deletions']}")
            if counts:
                details.append(", ".join(counts))
            lines.append(f"- `{raw_item.get('path', '')}` ({'; '.join(details)})")
    else:
        lines.append("- No changed file details were provided.")
    counts = _top_level_path_counts(files)
    if counts:
        lines.extend(["", "## Scope", ""])
        for root, count in sorted(counts.items()):
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


def _task_has_open_pr(task: TaskRecord) -> bool:
    promotion = task.get("promotion", {})
    return (
        isinstance(promotion, dict)
        and promotion.get("pr_number") not in (None, "")
        and bool(str(promotion.get("pr_url") or "").strip())
    )


def _default_promotion_title(task: Mapping[str, object]) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "task").strip().replace("-", " ")
    return f"{task_id}: {slug}" if task_id else (slug or "Sisyphus promotion")


def _default_commit_message(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    return f"{task_id}: {title}" if task_id else title


def _default_promotion_body(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "").strip()
    verify_status = str(task.get("verify_status") or "not_run").strip() or "not_run"
    lines = ["## Summary", "", f"- Promote task `{task_id}`"]
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


def _pull_request_number_from_url(url: str | None) -> int | None:
    match = re.search(r"/pull/(\d+)(?:$|[?#])", str(url or ""))
    return int(match.group(1)) if match else None


def _repo_full_name_from_remote_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if normalized.startswith("git@github.com:"):
        repo = normalized.split(":", 1)[1]
    elif "github.com/" in normalized:
        repo = normalized.split("github.com/", 1)[1]
    else:
        return None
    repo = repo.strip().rstrip("/")
    return (repo[:-4] if repo.endswith(".git") else repo) or None


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


__all__ = [
    "DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH",
    "PromotionExecutionError",
    "PromotionService",
]
