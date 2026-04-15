from __future__ import annotations

from dataclasses import dataclass

from .harness import EvolutionHarnessPlan
from ..utils import utc_now


EVOLUTION_CONSTRAINT_STATUS_ACCEPTED = "accepted"
EVOLUTION_CONSTRAINT_STATUS_PENDING = "pending"
EVOLUTION_CONSTRAINT_STATUS_REJECTED = "rejected"

EVOLUTION_GUARD_STATUS_PASSED = "passed"
EVOLUTION_GUARD_STATUS_PENDING = "pending"
EVOLUTION_GUARD_STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EvolutionGuardResult:
    guard_id: str
    title: str
    status: str
    blocking: bool
    baseline_value: object | None
    candidate_value: object | None
    detail: str


@dataclass(frozen=True, slots=True)
class EvolutionConstraintResult:
    run_id: str
    evaluated_at: str
    status: str
    accepted: bool | None
    warning_increase_threshold: int
    baseline_evaluation_id: str
    candidate_evaluation_id: str
    blocking_failure_count: int
    pending_guard_count: int
    checks: tuple[EvolutionGuardResult, ...]
    notes: str


def evaluate_evolution_constraints(
    plan: EvolutionHarnessPlan,
    *,
    warning_increase_threshold: int = 0,
    mcp_compatibility_ok: bool | None = None,
    output_contract_stable: bool | None = None,
    evaluated_at: str | None = None,
) -> EvolutionConstraintResult:
    if warning_increase_threshold < 0:
        raise ValueError("warning increase threshold must be zero or greater")

    baseline_metrics = plan.baseline.metrics
    candidate_metrics = plan.candidate.metrics
    checks = (
        _non_regression_guard(
            guard_id="verify-pass-rate",
            title="Verify Pass Rate",
            baseline_value=baseline_metrics.verify_pass_rate,
            candidate_value=candidate_metrics.verify_pass_rate,
            formatter=_format_percentage,
        ),
        _non_regression_guard(
            guard_id="conformance-drift",
            title="Conformance Drift Count",
            baseline_value=baseline_metrics.drift_count,
            candidate_value=candidate_metrics.drift_count,
            formatter=_format_integer,
            smaller_is_better=True,
        ),
        _warning_guard(
            baseline_value=baseline_metrics.unresolved_warning_count,
            candidate_value=candidate_metrics.unresolved_warning_count,
            threshold=warning_increase_threshold,
        ),
        _boolean_guard(
            guard_id="mcp-compatibility",
            title="MCP Compatibility",
            value=mcp_compatibility_ok,
        ),
        _boolean_guard(
            guard_id="output-contract-stability",
            title="Output Contract Stability",
            value=output_contract_stable,
        ),
    )
    blocking_failure_count = sum(1 for check in checks if check.blocking and check.status == EVOLUTION_GUARD_STATUS_FAILED)
    pending_guard_count = sum(1 for check in checks if check.status == EVOLUTION_GUARD_STATUS_PENDING)
    if blocking_failure_count:
        status = EVOLUTION_CONSTRAINT_STATUS_REJECTED
        accepted: bool | None = False
        notes = "candidate rejected because at least one blocking guard failed"
    elif pending_guard_count:
        status = EVOLUTION_CONSTRAINT_STATUS_PENDING
        accepted = None
        notes = "guard evaluation is incomplete until all required regression checks are populated"
    else:
        status = EVOLUTION_CONSTRAINT_STATUS_ACCEPTED
        accepted = True
        notes = "candidate satisfies the configured hard guards"

    return EvolutionConstraintResult(
        run_id=plan.run_id,
        evaluated_at=evaluated_at or utc_now(),
        status=status,
        accepted=accepted,
        warning_increase_threshold=warning_increase_threshold,
        baseline_evaluation_id=plan.baseline.evaluation_id,
        candidate_evaluation_id=plan.candidate.evaluation_id,
        blocking_failure_count=blocking_failure_count,
        pending_guard_count=pending_guard_count,
        checks=checks,
        notes=notes,
    )


def _non_regression_guard(
    *,
    guard_id: str,
    title: str,
    baseline_value: object | None,
    candidate_value: object | None,
    formatter,
    smaller_is_better: bool = False,
) -> EvolutionGuardResult:
    baseline_number = _coerce_float(baseline_value)
    candidate_number = _coerce_float(candidate_value)
    if baseline_number is None or candidate_number is None:
        detail = f"{title.lower()} guard is pending until both baseline and candidate metrics are available"
        return EvolutionGuardResult(
            guard_id=guard_id,
            title=title,
            status=EVOLUTION_GUARD_STATUS_PENDING,
            blocking=True,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            detail=detail,
        )

    passed = candidate_number <= baseline_number if smaller_is_better else candidate_number >= baseline_number
    relation = "did not regress" if passed else "regressed"
    detail = (
        f"{title.lower()} {relation}: baseline={formatter(baseline_number)}, "
        f"candidate={formatter(candidate_number)}"
    )
    return EvolutionGuardResult(
        guard_id=guard_id,
        title=title,
        status=EVOLUTION_GUARD_STATUS_PASSED if passed else EVOLUTION_GUARD_STATUS_FAILED,
        blocking=True,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        detail=detail,
    )


def _warning_guard(
    *,
    baseline_value: object | None,
    candidate_value: object | None,
    threshold: int,
) -> EvolutionGuardResult:
    baseline_count = _coerce_int(baseline_value)
    candidate_count = _coerce_int(candidate_value)
    if baseline_count is None or candidate_count is None:
        return EvolutionGuardResult(
            guard_id="unresolved-warnings",
            title="Unresolved Warnings",
            status=EVOLUTION_GUARD_STATUS_PENDING,
            blocking=True,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            detail="unresolved warning guard is pending until both baseline and candidate counts are available",
        )

    delta = candidate_count - baseline_count
    passed = delta <= threshold
    threshold_text = f"+{threshold}" if threshold else "0"
    detail = (
        "unresolved warning guard "
        f"{'passed' if passed else 'failed'}: baseline={baseline_count}, candidate={candidate_count}, "
        f"allowed increase={threshold_text}"
    )
    return EvolutionGuardResult(
        guard_id="unresolved-warnings",
        title="Unresolved Warnings",
        status=EVOLUTION_GUARD_STATUS_PASSED if passed else EVOLUTION_GUARD_STATUS_FAILED,
        blocking=True,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        detail=detail,
    )


def _boolean_guard(*, guard_id: str, title: str, value: bool | None) -> EvolutionGuardResult:
    if value is None:
        return EvolutionGuardResult(
            guard_id=guard_id,
            title=title,
            status=EVOLUTION_GUARD_STATUS_PENDING,
            blocking=True,
            baseline_value=None,
            candidate_value=None,
            detail=f"{title.lower()} guard is pending until the compatibility check is populated",
        )

    return EvolutionGuardResult(
        guard_id=guard_id,
        title=title,
        status=EVOLUTION_GUARD_STATUS_PASSED if value else EVOLUTION_GUARD_STATUS_FAILED,
        blocking=True,
        baseline_value=True,
        candidate_value=value,
        detail=f"{title.lower()} {'passed' if value else 'failed'}",
    )


def _coerce_float(value: object | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_int(value: object | None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _format_percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_integer(value: float) -> str:
    return str(int(value))
