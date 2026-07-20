from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import NoReturn

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
from ..commands.promotion import ExecutePromotionCommand
from ..external_review_verification import collect_external_review_evidence_gates
from ..planning_records import dedupe_gate_records, make_gate_record
from ..ports.artifacts import ArtifactStorePort
from ..ports.clock import ClockPort
from ..ports.promotion import (
    PromotionTaskPort,
    PullRequestPort,
    PullRequestSpec,
    VersionControlPort,
)
from ..ports.review import ExternalReviewEvidencePort
from ..ports.verification import VerificationConformancePort
from ..ports.workflow import TaskRecord
from ..promotion_projection import (
    DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH,
    build_execution_receipt,
    default_commit_message,
    default_promotion_body,
    default_promotion_title,
    optional_text,
    pull_request_number_from_url,
    repo_full_name_from_remote_url,
    task_has_open_pr,
)
from ..promotion_records import blocked_phase, blocked_stage, record_promotion_lifecycle_transition
from ..results.artifacts import ArtifactRef
from ..results.promotion import PromotionExecutionResult
from ..review_scope import (
    external_review_binding_is_current,
    external_review_post_promotion_paths,
    external_review_post_verification_paths,
    external_review_recorded_output_paths,
    PROMOTION_OUTPUT_PATHS_FIELD,
    validate_promotion_execution_receipt_path,
)


class PromotionExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class PromotionExecutionService:
    tasks: PromotionTaskPort
    version_control: VersionControlPort
    pull_requests: PullRequestPort
    artifacts: ArtifactStorePort
    conformance: VerificationConformancePort
    external_reviews: ExternalReviewEvidencePort | None
    clock: ClockPort

    def execute(self, command: ExecutePromotionCommand) -> PromotionExecutionResult:
        task = self.tasks.load(command.task_id)
        ensure_task_promotion_defaults(task)
        promotion = task["promotion"]
        if not bool(promotion.get("required")):
            raise ValueError(f"task `{command.task_id}` does not require promotion")
        review = _required_external_review(task)
        if review is not None and not external_review_binding_is_current(task):
            self._block_for_stale_review(
                task,
                promotion,
                message="verification is not bound to the current external review",
            )

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
        persisted_head_sha = str(promotion.get("head_sha") or "").strip()
        if current_status in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED}:
            raise ValueError(f"task `{command.task_id}` is already merged or promotion-recorded")

        workspace = str(task.get("worktree_path") or "")
        if not self.version_control.workspace_exists(workspace):
            raise FileNotFoundError(f"task worktree does not exist: {workspace}")
        reviewed_commit_sha: str | None = None
        if review is not None:
            external_reviews = self.external_reviews
            if external_reviews is None:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="external review evidence adapter is unavailable",
                )
            try:
                allowed_generated_paths = (
                    *external_review_post_verification_paths(task, review),
                    *external_review_post_promotion_paths(task, review),
                )
            except (TypeError, ValueError):
                allowed_generated_paths = ()
            review_gates = collect_external_review_evidence_gates(
                task,
                review,
                evidence=external_reviews,
                gate=lambda code, message, source: make_gate_record(
                    code,
                    message,
                    source,
                    created_at=self.clock.now(),
                ),
                additional_allowed_dirty_paths=allowed_generated_paths,
            )
            if review_gates:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="external review evidence changed after verification",
                    gates=review_gates,
                )
            reviewed_commit_sha = str(review["reviewed_head_sha"]).strip().lower()
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
        if review is not None:
            reviewed_base = self.resolve_base(task)
            reviewed_remote = str(promotion.get("remote_name") or "origin").strip()
            reviewed_head = (
                str(promotion.get("head_branch") or "").strip()
                or str(task.get("branch") or "").strip()
            )
            if remote != reviewed_remote:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="promotion remote differs from the externally reviewed target",
                )
            if head_branch != reviewed_head:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="promotion head branch differs from the externally reviewed target",
                )
            if base.base_branch != reviewed_base.base_branch:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="promotion base branch differs from the externally reviewed target",
                )
        title = str(command.title or "").strip() or default_promotion_title(task)
        body = str(command.body or "").strip() or default_promotion_body(task, title=title)
        commit_message = (
            str(command.commit_message or "").strip()
            or default_commit_message(task, title=title)
        )
        configured_repo_full_name = str(promotion.get("repo_full_name") or "").strip()
        remote_repo_full_name = str(
            repo_full_name_from_remote_url(
                self.version_control.remote_url(workspace, remote)
            )
            or ""
        )
        requested_repo_full_name = str(command.repo_full_name or "").strip()
        repo_full_name = (
            requested_repo_full_name
            or configured_repo_full_name
            or remote_repo_full_name
        )
        if review is not None:
            reviewed_repo_full_name = configured_repo_full_name or remote_repo_full_name
            if requested_repo_full_name and (
                not reviewed_repo_full_name
                or requested_repo_full_name.casefold()
                != reviewed_repo_full_name.casefold()
            ):
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="promotion repository differs from the externally reviewed target",
                )
            recorded_receipt_paths = external_review_recorded_output_paths(
                review,
                field=PROMOTION_OUTPUT_PATHS_FIELD,
            )
            if len(recorded_receipt_paths) != 1:
                self._block_for_stale_review(
                    task,
                    promotion,
                    message="external review must bind exactly one promotion receipt",
                )
            receipt_path = recorded_receipt_paths[0]
        else:
            receipt_path = str(
                promotion.get("execution_receipt_path")
                or DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH
            )
        receipt_path = validate_promotion_execution_receipt_path(task, receipt_path)
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

        head_requires_push = False
        if reviewed_commit_sha is not None:
            commit_sha = reviewed_commit_sha
            promotion["head_sha"] = commit_sha
        else:
            commit_sha = str(promotion.get("head_sha") or "").strip()
            resume_existing_head = False
            if (
                current_status
                in {
                    PROMOTION_STATUS_COMMITTED,
                    PROMOTION_STATUS_PUSHED,
                    PROMOTION_STATUS_PR_OPEN,
                }
                and persisted_head_sha
            ):
                workspace_head_sha = self.version_control.current_head(workspace).strip()
                dirty_paths = set(self.version_control.dirty_paths(workspace))
                generated_paths = _promotion_retry_generated_paths(task, receipt_path)
                resume_existing_head = (
                    workspace_head_sha == persisted_head_sha
                    and dirty_paths.issubset(generated_paths)
                )
            if not resume_existing_head:
                self.version_control.stage_all(workspace)
            staged_changes = (
                False
                if resume_existing_head
                else self.version_control.has_staged_changes(workspace)
            )
            if staged_changes:
                commit_sha = self.version_control.commit(workspace, commit_message)
                head_requires_push = True
                promotion.update(
                    {
                        "required": True,
                        "status": PROMOTION_STATUS_COMMITTED,
                        "head_sha": commit_sha,
                        "commit_message": commit_message,
                        "committed_at": self.clock.now(),
                    }
                )
                self.tasks.save_promotion_state(task)
                self._write_execution_receipt(task, receipt_path, draft=command.draft)
            elif persisted_head_sha:
                workspace_head_sha = self.version_control.current_head(workspace).strip()
                if not workspace_head_sha:
                    raise PromotionExecutionError("working tree HEAD could not be resolved")
                commit_sha = workspace_head_sha
                if commit_sha != persisted_head_sha:
                    head_requires_push = True
                    promotion.update(
                        {
                            "required": True,
                            "status": PROMOTION_STATUS_COMMITTED,
                            "head_sha": commit_sha,
                            "commit_message": commit_message,
                            "committed_at": self.clock.now(),
                            "pushed_at": None,
                        }
                    )
                    self.tasks.save_promotion_state(task)
                    self._write_execution_receipt(task, receipt_path, draft=command.draft)
            else:
                raise PromotionExecutionError("no staged changes available for promotion")

        already_pushed = (
            not head_requires_push
            and current_status in {PROMOTION_STATUS_PUSHED, PROMOTION_STATUS_PR_OPEN}
            and persisted_head_sha == commit_sha
            and bool(promotion.get("pushed_at"))
        )
        if not already_pushed:
            if reviewed_commit_sha is not None:
                self.version_control.push_revision(
                    workspace,
                    remote,
                    reviewed_commit_sha,
                    head_branch,
                )
            else:
                self.version_control.push(workspace, remote, head_branch)
            promotion["status"] = (
                PROMOTION_STATUS_PR_OPEN if task_has_open_pr(task) else PROMOTION_STATUS_PUSHED
            )
            promotion["head_sha"] = commit_sha
            promotion["pushed_at"] = self.clock.now()
            self.tasks.save_promotion_state(task)
            self._write_execution_receipt(task, receipt_path, draft=command.draft)

        if not task_has_open_pr(task):
            pull_request_spec = PullRequestSpec(
                workspace=workspace,
                repo_full_name=repo_full_name or None,
                base_branch=base.base_branch,
                head_branch=head_branch,
                title=title,
                body=body,
                draft=command.draft,
            )
            pr_url = None
            if current_status in {PROMOTION_STATUS_PUSHED, PROMOTION_STATUS_PR_OPEN}:
                pr_url = self.pull_requests.find_open(pull_request_spec)
            if pr_url is None:
                pr_url = self.pull_requests.create(pull_request_spec)
            promotion["status"] = PROMOTION_STATUS_PR_OPEN
            promotion["pr_url"] = pr_url
            promotion["pr_number"] = pull_request_number_from_url(pr_url)
            promotion["pr_opened_at"] = self.clock.now()
            self.tasks.save_promotion_state(task)
            self._write_execution_receipt(task, receipt_path, draft=command.draft)
        else:
            self._write_execution_receipt(task, receipt_path, draft=command.draft)

        return PromotionExecutionResult(
            task_id=str(task["id"]),
            branch=str(task.get("branch") or head_branch),
            base_branch=base.base_branch,
            head_branch=head_branch,
            status=str(promotion["status"]),
            commit_sha=str(promotion["head_sha"]),
            pr_number=(
                int(promotion["pr_number"])
                if promotion.get("pr_number") is not None
                else None
            ),
            pr_url=(str(promotion["pr_url"]) if promotion.get("pr_url") else None),
            receipt=ArtifactRef(relative_path=receipt_path),
        )

    def _block_for_stale_review(
        self,
        task: TaskRecord,
        promotion: dict,
        *,
        message: str,
        gates: list[dict] | None = None,
    ) -> NoReturn:
        blocked_at = self.clock.now()
        task["verify_status"] = "not_run"
        task["last_verified_at"] = None
        task["last_verify_results"] = []
        task["status"] = "blocked"
        task["stage"] = "audit"
        task["workflow_phase"] = "execution"
        promotion["reverify_required"] = True
        task["updated_at"] = blocked_at
        stale_gates = gates or [
            make_gate_record(
                "EXTERNAL_LLM_REVIEW_STALE",
                message,
                "promotion",
                created_at=blocked_at,
            )
        ]
        task["gates"] = dedupe_gate_records(
            [*task.get("gates", []), *stale_gates]
        )
        self.tasks.save(task)
        raise ValueError(f"promotion blocked: {message}")

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
                parent_task_id=optional_text(promotion.get("parent_task_id")),
                parent_artifact_id=optional_text(promotion.get("parent_artifact_id")),
                parent_branch=None,
            )

        strategy = str(promotion.get("strategy") or "").strip().lower()
        parent_task_id = optional_text(promotion.get("parent_task_id"))
        parent_artifact_id = optional_text(promotion.get("parent_artifact_id"))
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

    def _write_execution_receipt(self, task: TaskRecord, path: str, *, draft: bool) -> None:
        self.artifacts.write_json(
            str(task["id"]),
            path,
            build_execution_receipt(task, draft=draft, written_at=self.clock.now()),
        )


def _required_external_review(task: TaskRecord) -> dict | None:
    strategy = task.get("test_strategy")
    if not isinstance(strategy, dict):
        return None
    review = strategy.get("external_llm")
    if not isinstance(review, dict) or not review.get("required"):
        return None
    return review


def _promotion_retry_generated_paths(task: TaskRecord, receipt_path: str) -> set[str]:
    raw_task_dir = str(task.get("task_dir") or "").strip()
    task_dir = PurePosixPath(raw_task_dir)
    if (
        not raw_task_dir
        or task_dir.is_absolute()
        or ".." in task_dir.parts
        or raw_task_dir != task_dir.as_posix()
    ):
        return set()
    return {
        (task_dir / "task.json").as_posix(),
        (task_dir / receipt_path).as_posix(),
    }


__all__ = ["PromotionExecutionError", "PromotionExecutionService"]
