from __future__ import annotations

from collections.abc import Callable, Iterable

from .ports.review import ExternalReviewEvidenceError, ExternalReviewEvidencePort
from .ports.workflow import TaskRecord
from .review_scope import external_review_binding, validate_external_review_output_paths


GateFactory = Callable[[str, str, str], dict]


def collect_external_review_evidence_gates(
    task: TaskRecord,
    review: dict,
    *,
    evidence: ExternalReviewEvidencePort,
    gate: GateFactory,
    additional_allowed_dirty_paths: Iterable[str] = (),
) -> list[dict]:
    report_path = str(review.get("report_path") or "").strip()
    envelope_path = str(review.get("envelope_path") or "").strip()
    envelope_digest = str(review.get("envelope_digest") or "").strip().lower()
    scope_digest = str(review.get("scope_digest") or "").strip().lower()
    reviewed_head_sha = str(review.get("reviewed_head_sha") or "").strip().lower()
    report_digest = str(review.get("report_digest") or "").strip().lower()
    workspace = str(task.get("worktree_path") or "").strip()
    if not all(
        (
            envelope_path,
            envelope_digest,
            report_path,
            report_digest,
            reviewed_head_sha,
            scope_digest,
            workspace,
        )
    ):
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                "external LLM review is missing head-bound evidence metadata",
                "strategy",
            )
        ]
    try:
        validate_external_review_output_paths(task, review)
    except (TypeError, ValueError) as exc:
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                f"external LLM review output paths are stale: {exc}",
                "strategy",
            )
        ]
    try:
        inspected = evidence.inspect(workspace, envelope_path, task)
    except ExternalReviewEvidenceError as exc:
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                f"external LLM review evidence is unavailable: {exc}",
                "strategy",
            )
        ]
    if inspected.current_head_sha.lower() != reviewed_head_sha:
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                "external LLM review does not cover the current Git HEAD",
                "strategy",
            )
        ]
    if inspected.report_digest.lower() != report_digest:
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                "external LLM review report digest no longer matches",
                "strategy",
            )
        ]

    expected_metadata = {
        "provider": inspected.provider,
        "reviewer": inspected.reviewer,
        "envelope_path": inspected.envelope_path,
        "envelope_digest": inspected.envelope_digest,
        "report_path": inspected.report_path,
        "report_digest": inspected.report_digest,
        "reviewed_head_sha": inspected.reviewed_head_sha,
        "scope_digest": inspected.scope_digest,
        "finding_count": inspected.finding_count,
        "blocking_finding_count": inspected.blocking_finding_count,
    }
    for field, actual in expected_metadata.items():
        expected = review.get(field)
        if isinstance(actual, str):
            matches = str(expected or "").strip().lower() == actual.lower()
        else:
            matches = expected == actual
        if not matches:
            return [
                gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    f"external LLM review {field} no longer matches its envelope",
                    "strategy",
                )
            ]
    if inspected.status != "passed":
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                "external LLM review envelope contains blocking findings",
                "strategy",
            )
        ]
    if inspected.current_scope_digest.lower() != scope_digest:
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                "external LLM review does not cover the current task and verification scope",
                "strategy",
            )
        ]

    task_dir = str(task.get("task_dir") or "").strip().rstrip("/")
    allowed_dirty_paths = {
        inspected.envelope_path,
        inspected.report_path,
        f"{task_dir}/task.json",
        *additional_allowed_dirty_paths,
    }
    unrelated = [
        path for path in inspected.dirty_paths if path not in allowed_dirty_paths
    ]
    if unrelated:
        detail = ", ".join(unrelated[:5])
        return [
            gate(
                "EXTERNAL_LLM_REVIEW_STALE",
                f"external LLM review does not cover workspace changes: {detail}",
                "strategy",
            )
        ]
    return []


def record_external_review_verification_binding(
    task: TaskRecord,
    *,
    passed: bool,
    verified_at: str,
) -> None:
    strategy = task.get("test_strategy")
    if not isinstance(strategy, dict):
        return
    review = strategy.get("external_llm")
    if not isinstance(review, dict) or not review.get("required"):
        return
    if not passed:
        review.pop("verification_binding", None)
        return
    review["verification_binding"] = external_review_binding(
        review,
        verified_at=verified_at,
    )
    promotion = task.get("promotion")
    if isinstance(promotion, dict) and promotion.get("required"):
        promotion["reverify_required"] = False


__all__ = [
    "collect_external_review_evidence_gates",
    "record_external_review_verification_binding",
]
