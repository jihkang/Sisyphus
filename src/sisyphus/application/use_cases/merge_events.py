from __future__ import annotations

from dataclasses import dataclass

from ...shared.mappings import project_fields
from ..commands.promotion import RecordMergedPullRequestCommand
from ..ports.inbox_handlers import PromotionMergePort
from ..ports.workflow import EventPublisherPort, WorkflowEvent
from ..results.inbox_handlers import PromotionMergeReceipt


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
class PullRequestMergedEventService:
    promotions: PromotionMergePort
    events: EventPublisherPort

    def process(self, event: dict[str, object]) -> dict[str, object]:
        payload = project_fields(
            event.get("payload", {}),
            PULL_REQUEST_MERGED_FIELD_DEFAULTS,
        )
        outcome = self.promotions.record(
            RecordMergedPullRequestCommand(
                task_id=str(payload["task_id"]) if payload.get("task_id") else None,
                branch=str(payload["branch"]) if payload.get("branch") else None,
                repo_full_name=(
                    str(payload["repo_full_name"])
                    if payload.get("repo_full_name")
                    else None
                ),
                pr_number=int(payload["pr_number"]),
                title=str(payload["title"]),
                url=str(payload["url"]) if payload.get("url") else None,
                base_branch=(
                    str(payload["base_branch"])
                    if payload.get("base_branch")
                    else None
                ),
                head_branch=(
                    str(payload["head_branch"])
                    if payload.get("head_branch")
                    else None
                ),
                head_sha=str(payload["head_sha"]) if payload.get("head_sha") else None,
                merge_commit_sha=(
                    str(payload["merge_commit_sha"])
                    if payload.get("merge_commit_sha")
                    else None
                ),
                merged_at=(
                    str(payload["merged_at"]) if payload.get("merged_at") else None
                ),
                merged_by=(
                    str(payload["merged_by"]) if payload.get("merged_by") else None
                ),
                merge_method=(
                    str(payload["merge_method"])
                    if payload.get("merge_method")
                    else None
                ),
                additions=(
                    int(payload["additions"])
                    if payload.get("additions") is not None
                    else None
                ),
                deletions=(
                    int(payload["deletions"])
                    if payload.get("deletions") is not None
                    else None
                ),
                changed_files=tuple(
                    dict(item)
                    for item in payload.get("changed_files", [])
                    if isinstance(item, dict)
                ),
            )
        )
        data = _outcome_record(outcome)
        self.events.publish(
            WorkflowEvent(
                event_type="promotion.recorded",
                source={"module": "daemon"},
                data={"promotion_kind": "pull_request_merge", **data},
            )
        )
        return data


def _outcome_record(outcome: PromotionMergeReceipt) -> dict[str, object]:
    return {
        "task_id": outcome.task_id,
        "branch": outcome.branch,
        "pr_number": outcome.pr_number,
        "title": outcome.title,
        "recorded_at": outcome.recorded_at,
        "receipt_path": outcome.receipt_path,
        "changeset_path": outcome.changeset_path,
        "close_attempted": outcome.close_attempted,
        "closed": outcome.closed,
        "close_status": outcome.close_status,
        "close_gate_codes": list(outcome.close_gate_codes),
        "child_retargeted_task_ids": list(outcome.child_retargeted_task_ids),
    }


__all__ = ["PullRequestMergedEventService"]
