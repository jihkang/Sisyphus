from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from ..commands.review import RecordExternalReviewCommand
from ..ports.clock import ClockPort
from ..ports.review import ExternalReviewEvidencePort
from ..ports.workflow import TaskRecordPort
from ..results.review import ExternalReviewRecordResult


_GIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40,64}$")
_REVIEW_POLICY_FIELDS = ("required", "provider", "purpose", "trigger")


@dataclass(slots=True)
class ExternalReviewService:
    tasks: TaskRecordPort
    evidence: ExternalReviewEvidencePort
    clock: ClockPort

    def record(
        self,
        command: RecordExternalReviewCommand,
    ) -> ExternalReviewRecordResult:
        task_id = _required_text(command.task_id, field="task_id")
        reviewer = _required_text(command.reviewer, field="reviewer")
        verdict = _normalize_verdict(command.verdict)
        report_path = _normalize_report_path(command.report_path)
        reviewed_head_sha = _normalize_head_sha(command.reviewed_head_sha)
        finding_count = _non_negative(command.finding_count, field="finding_count")
        blocking_finding_count = _non_negative(
            command.blocking_finding_count,
            field="blocking_finding_count",
        )
        if blocking_finding_count > finding_count:
            raise ValueError("blocking_finding_count cannot exceed finding_count")
        if verdict == "pass" and blocking_finding_count:
            raise ValueError("a passing external review cannot contain blocking findings")

        task = self.tasks.load(task_id)
        review, provider, workspace = _review_policy(task_id, task)
        policy_fingerprint = tuple(review.get(field) for field in _REVIEW_POLICY_FIELDS)

        inspected = self.evidence.inspect(workspace, report_path)
        if inspected.current_head_sha.lower() != reviewed_head_sha.lower():
            raise ValueError(
                "external review is stale: reviewed head "
                f"{reviewed_head_sha} does not match current HEAD {inspected.current_head_sha}"
            )
        unrelated_dirty_paths = sorted(
            set(inspected.dirty_paths) - {inspected.relative_path}
        )
        if unrelated_dirty_paths:
            raise ValueError(
                "external review does not cover uncommitted workspace changes: "
                + ", ".join(unrelated_dirty_paths)
            )

        completed_at = self.clock.now()
        status = "passed" if verdict == "pass" else "failed"
        review_record = {
            "status": status,
            "provider": provider,
            "reviewer": reviewer,
            "reviewed_at": completed_at,
            "reviewed_head_sha": inspected.current_head_sha,
            "report_path": inspected.relative_path,
            "report_digest": inspected.digest,
            "report_size_bytes": inspected.size_bytes,
            "finding_count": finding_count,
            "blocking_finding_count": blocking_finding_count,
            "summary": _optional_text(command.summary),
        }

        def persist(latest: dict) -> None:
            latest_review, _, latest_workspace = _review_policy(task_id, latest)
            latest_policy = tuple(
                latest_review.get(field) for field in _REVIEW_POLICY_FIELDS
            )
            if latest_policy != policy_fingerprint or latest_workspace != workspace:
                raise ValueError("external review policy or worktree changed during recording")
            latest_review.update(review_record)

        self.tasks.update(task_id, persist)
        return ExternalReviewRecordResult(
            task_id=task_id,
            status=status,
            provider=provider,
            reviewer=reviewer,
            reviewed_head_sha=inspected.current_head_sha,
            report_path=inspected.relative_path,
            report_digest=inspected.digest,
            finding_count=finding_count,
            blocking_finding_count=blocking_finding_count,
            completed_at=completed_at,
        )


def _normalize_verdict(value: object) -> str:
    verdict = _required_text(value, field="verdict").lower()
    if verdict not in {"pass", "fail"}:
        raise ValueError("verdict must be `pass` or `fail`")
    return verdict


def _review_policy(task_id: str, task: dict) -> tuple[dict, str, str]:
    if str(task.get("status") or "") == "closed":
        raise ValueError(f"task `{task_id}` is already closed")
    strategy = task.get("test_strategy")
    if not isinstance(strategy, dict):
        raise ValueError(f"task `{task_id}` has no test strategy")
    review = strategy.get("external_llm")
    if not isinstance(review, dict) or not review.get("required"):
        raise ValueError(f"task `{task_id}` does not require an external LLM review")
    provider = _required_text(review.get("provider"), field="external review provider")
    workspace = _required_text(task.get("worktree_path"), field="task worktree_path")
    return review, provider, workspace


def _normalize_report_path(value: object) -> str:
    raw = _required_text(value, field="report_path")
    if "\\" in raw or "\x00" in raw:
        raise ValueError("report_path must be a relative POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise ValueError("report_path must be a contained relative path")
    normalized = path.as_posix()
    if normalized != raw or any(part in {"", "."} for part in path.parts):
        raise ValueError("report_path must be a normalized relative POSIX path")
    return normalized


def _normalize_head_sha(value: object) -> str:
    head_sha = _required_text(value, field="reviewed_head_sha")
    if not _GIT_SHA_PATTERN.fullmatch(head_sha):
        raise ValueError(
            "reviewed_head_sha must be a 40-64 character hexadecimal Git object ID"
        )
    return head_sha.lower()


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _non_negative(value: int, *, field: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field} must be non-negative")
    return normalized


__all__ = ["ExternalReviewService"]
