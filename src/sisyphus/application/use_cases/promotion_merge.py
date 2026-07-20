from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...domain.lifecycle import LifecycleAction
from ...domain.promotion import (
    PROMOTION_STATUS_MERGED,
    PROMOTION_STATUS_RECORDED,
    PROMOTION_STRATEGY_STACKED,
    ensure_task_promotion_defaults,
)
from ...domain.task.models import DEFAULT_CHANGESET_PATH, DEFAULT_PROMOTION_RECEIPT_PATH
from ..commands.promotion import RecordMergedPullRequestCommand
from ..ports.artifacts import ArtifactStorePort
from ..ports.clock import ClockPort
from ..ports.promotion import PromotionTaskPort, ReopenedTaskPort
from ..ports.verification import VerificationConformancePort
from ..ports.workflow import CloseoutPort, ManualInterventionPort, TaskRecord
from ..promotion_projection import (
    build_merge_receipt,
    normalize_changed_files,
    optional_text,
    render_changeset_markdown,
    resolve_total_count,
)
from ..promotion_records import record_promotion_lifecycle_transition
from ..results.promotion import MergeReceiptResult


@dataclass(slots=True)
class MergedPromotionRecorder:
    tasks: PromotionTaskPort
    artifacts: ArtifactStorePort
    conformance: VerificationConformancePort
    closeout: CloseoutPort
    interventions: ManualInterventionPort
    reopened_tasks: ReopenedTaskPort
    clock: ClockPort

    def record(self, command: RecordMergedPullRequestCommand) -> MergeReceiptResult:
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
        changed_files = normalize_changed_files(command.changed_files)
        additions = resolve_total_count(command.additions, changed_files, "additions")
        deletions = resolve_total_count(command.deletions, changed_files, "deletions")
        docs = dict(task.get("docs", {}))
        receipt_path = str(docs.get("promotion") or DEFAULT_PROMOTION_RECEIPT_PATH)
        changeset_path = str(docs.get("changeset") or DEFAULT_CHANGESET_PATH)
        receipt = build_merge_receipt(
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
            render_changeset_markdown(receipt),
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
            branch=optional_text(task.get("branch")),
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


__all__ = ["MergedPromotionRecorder"]
