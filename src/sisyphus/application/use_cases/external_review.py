from __future__ import annotations

from dataclasses import dataclass

from ..commands.review import RecordExternalReviewCommand
from ..planning_records import dedupe_gate_records, make_gate_record
from ..ports.clock import ClockPort
from ..ports.review import ExternalReviewEvidencePort
from ..ports.workflow import TaskRecordPort
from ..results.review import ExternalReviewRecordResult, ExternalReviewScopeResult
from ..review_scope import external_review_scope_digest


_REVIEW_POLICY_FIELDS = ("required", "provider", "purpose", "trigger")
_REVIEW_GATE_CODES = {
    "EXTERNAL_LLM_REVIEW_REQUIRED",
    "EXTERNAL_LLM_REVIEW_STALE",
    "VERIFY_REQUIRED",
}


@dataclass(slots=True)
class ExternalReviewService:
    tasks: TaskRecordPort
    evidence: ExternalReviewEvidencePort
    clock: ClockPort

    def scope(self, task_id: str) -> ExternalReviewScopeResult:
        normalized_task_id = _required_text(task_id, field="task_id")
        task = self.tasks.load(normalized_task_id)
        _review, _provider, workspace = _review_policy(normalized_task_id, task)
        inspected = self.evidence.scope(workspace, task)
        return ExternalReviewScopeResult(
            task_id=normalized_task_id,
            current_head_sha=inspected.current_head_sha,
            scope_digest=inspected.scope_digest,
            document_digests=inspected.document_digests,
        )

    def record(
        self,
        command: RecordExternalReviewCommand,
    ) -> ExternalReviewRecordResult:
        task_id = _required_text(command.task_id, field="task_id")
        envelope_path = _required_text(command.envelope_path, field="envelope_path")
        task = self.tasks.load(task_id)
        review, provider, workspace = _review_policy(task_id, task)
        policy_fingerprint = tuple(review.get(field) for field in _REVIEW_POLICY_FIELDS)

        inspected = self.evidence.inspect(workspace, envelope_path, task)
        if inspected.provider != provider:
            raise ValueError(
                "external review provider does not match the frozen review policy: "
                f"{inspected.provider!r} != {provider!r}"
            )
        if inspected.reviewed_head_sha != inspected.current_head_sha:
            raise ValueError(
                "external review is stale: reviewed head "
                f"{inspected.reviewed_head_sha} does not match current HEAD "
                f"{inspected.current_head_sha}"
            )
        if inspected.scope_digest != inspected.current_scope_digest:
            raise ValueError(
                "external review is stale: envelope scope does not match the current frozen task scope"
            )
        unrelated_dirty_paths = sorted(
            set(inspected.dirty_paths)
            - {inspected.envelope_path, inspected.report_path}
        )
        if unrelated_dirty_paths:
            raise ValueError(
                "external review does not cover uncommitted workspace changes: "
                + ", ".join(unrelated_dirty_paths)
            )

        completed_at = self.clock.now()
        status = inspected.status
        review_record = {
            "status": status,
            "provider": inspected.provider,
            "reviewer": inspected.reviewer,
            "reviewed_at": completed_at,
            "reviewed_head_sha": inspected.current_head_sha,
            "scope_digest": inspected.scope_digest,
            "envelope_path": inspected.envelope_path,
            "envelope_digest": inspected.envelope_digest,
            "envelope_size_bytes": inspected.envelope_size_bytes,
            "report_path": inspected.report_path,
            "report_digest": inspected.report_digest,
            "report_size_bytes": inspected.report_size_bytes,
            "finding_count": inspected.finding_count,
            "blocking_finding_count": inspected.blocking_finding_count,
            "findings": [
                {
                    "id": finding.finding_id,
                    "severity": finding.severity,
                    "title": finding.title,
                    "detail": finding.detail,
                    "blocking": finding.blocking,
                }
                for finding in inspected.findings
            ],
            "summary": inspected.summary,
        }

        def persist(latest: dict) -> None:
            latest_review, _, latest_workspace = _review_policy(task_id, latest)
            latest_policy = tuple(
                latest_review.get(field) for field in _REVIEW_POLICY_FIELDS
            )
            latest_scope_digest = external_review_scope_digest(
                latest,
                dict(inspected.document_digests),
            )
            if (
                latest_policy != policy_fingerprint
                or latest_workspace != workspace
                or latest_scope_digest != inspected.current_scope_digest
            ):
                raise ValueError(
                    "external review policy, scope, or worktree changed during recording"
                )
            confirmed = self.evidence.inspect(
                latest_workspace,
                inspected.envelope_path,
                latest,
            )
            if confirmed != inspected:
                raise ValueError(
                    "external review evidence or workspace changed during recording"
                )
            latest_review.pop("verification_binding", None)
            latest_review.update(review_record)
            _invalidate_verification(latest, status=status, created_at=completed_at)

        self.tasks.update(task_id, persist)
        return ExternalReviewRecordResult(
            task_id=task_id,
            status=status,
            provider=inspected.provider,
            reviewer=inspected.reviewer,
            reviewed_head_sha=inspected.current_head_sha,
            scope_digest=inspected.scope_digest,
            envelope_path=inspected.envelope_path,
            envelope_digest=inspected.envelope_digest,
            report_path=inspected.report_path,
            report_digest=inspected.report_digest,
            finding_count=inspected.finding_count,
            blocking_finding_count=inspected.blocking_finding_count,
            completed_at=completed_at,
        )


def _invalidate_verification(task: dict, *, status: str, created_at: str) -> None:
    task["verify_status"] = "not_run"
    task["last_verified_at"] = None
    task["last_verify_results"] = []
    task["status"] = "blocked"
    task["stage"] = "audit"
    task["workflow_phase"] = "execution"
    task["updated_at"] = created_at

    promotion = task.get("promotion")
    if isinstance(promotion, dict) and promotion.get("required"):
        promotion["reverify_required"] = True

    gates = [
        gate
        for gate in task.get("gates", [])
        if gate.get("code") not in _REVIEW_GATE_CODES
        and gate.get("source") != "review"
    ]
    if status == "passed":
        gates.append(
            make_gate_record(
                "VERIFY_REQUIRED",
                "task must be verified against the recorded external review",
                "review",
                created_at=created_at,
            )
        )
    else:
        gates.append(
            make_gate_record(
                "EXTERNAL_LLM_REVIEW_REQUIRED",
                "external LLM review contains blocking findings",
                "review",
                created_at=created_at,
            )
        )
    task["gates"] = dedupe_gate_records(gates)


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


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text


__all__ = ["ExternalReviewService"]
