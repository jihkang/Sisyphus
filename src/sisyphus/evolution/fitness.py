from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from ..conformance import CONFORMANCE_GREEN, CONFORMANCE_RED, CONFORMANCE_YELLOW, normalize_conformance_status
from .constraints import EVOLUTION_CONSTRAINT_STATUS_REJECTED, EvolutionConstraintResult
from .harness import EvolutionHarnessPlan, EvolutionPlannedMetrics


EVOLUTION_FITNESS_STATUS_PENDING = "pending"
EVOLUTION_FITNESS_STATUS_REJECTED = "rejected"
EVOLUTION_FITNESS_STATUS_SCORED = "scored"

EVOLUTION_METRIC_STATUS_PENDING = "pending"
EVOLUTION_METRIC_STATUS_SCORED = "scored"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class EvolutionMetricComparison:
    metric_id: str
    title: str
    weight: float
    status: str
    baseline_value: object | None
    candidate_value: object | None
    baseline_score: float | None
    candidate_score: float | None
    score_delta: float | None
    detail: str


@dataclass(frozen=True, slots=True)
class EvolutionFitnessResult:
    run_id: str
    evaluated_at: str
    status: str
    eligible_for_promotion: bool | None
    comparable_metric_count: int
    baseline_score: float | None
    candidate_score: float | None
    score_delta: float | None
    comparisons: tuple[EvolutionMetricComparison, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class _MetricSpec:
    metric_id: str
    title: str
    weight: float
    extractor: Callable[[EvolutionPlannedMetrics], object | None]
    normalizer: Callable[[object | None], float | None]


def evaluate_evolution_fitness(
    plan: EvolutionHarnessPlan,
    *,
    constraints: EvolutionConstraintResult | None = None,
    evaluated_at: str | None = None,
) -> EvolutionFitnessResult:
    comparisons = tuple(_build_metric_comparison(spec, plan.baseline.metrics, plan.candidate.metrics) for spec in _METRIC_SPECS)
    scored_comparisons = tuple(comparison for comparison in comparisons if comparison.status == EVOLUTION_METRIC_STATUS_SCORED)
    comparable_metric_count = len(scored_comparisons)
    total_weight = sum(comparison.weight for comparison in scored_comparisons)

    baseline_score = None
    candidate_score = None
    score_delta = None
    if total_weight:
        baseline_score = round(sum((comparison.baseline_score or 0.0) * comparison.weight for comparison in scored_comparisons) / total_weight, 2)
        candidate_score = round(sum((comparison.candidate_score or 0.0) * comparison.weight for comparison in scored_comparisons) / total_weight, 2)
        score_delta = round(candidate_score - baseline_score, 2)

    if constraints is not None and constraints.status == EVOLUTION_CONSTRAINT_STATUS_REJECTED:
        status = EVOLUTION_FITNESS_STATUS_REJECTED
        eligible_for_promotion: bool | None = False
        notes = "candidate is not eligible for promotion because hard guards failed"
    elif comparable_metric_count == 0:
        status = EVOLUTION_FITNESS_STATUS_PENDING
        eligible_for_promotion = None
        notes = "fitness scoring is pending until comparable baseline and candidate metrics are available"
    else:
        status = EVOLUTION_FITNESS_STATUS_SCORED
        eligible_for_promotion = None if constraints is None else constraints.accepted
        notes = "fitness scoring is derived from the comparable harness metrics available in this slice"

    return EvolutionFitnessResult(
        run_id=plan.run_id,
        evaluated_at=evaluated_at or utc_now(),
        status=status,
        eligible_for_promotion=eligible_for_promotion,
        comparable_metric_count=comparable_metric_count,
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        score_delta=score_delta,
        comparisons=comparisons,
        notes=notes,
    )


def _build_metric_comparison(
    spec: _MetricSpec,
    baseline_metrics: EvolutionPlannedMetrics,
    candidate_metrics: EvolutionPlannedMetrics,
) -> EvolutionMetricComparison:
    baseline_value = spec.extractor(baseline_metrics)
    candidate_value = spec.extractor(candidate_metrics)
    baseline_norm = spec.normalizer(baseline_value)
    candidate_norm = spec.normalizer(candidate_value)
    if baseline_norm is None or candidate_norm is None:
        detail = f"{spec.title.lower()} is pending until both baseline and candidate values are available"
        return EvolutionMetricComparison(
            metric_id=spec.metric_id,
            title=spec.title,
            weight=spec.weight,
            status=EVOLUTION_METRIC_STATUS_PENDING,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            baseline_score=None,
            candidate_score=None,
            score_delta=None,
            detail=detail,
        )

    baseline_score = round(baseline_norm * 100, 2)
    candidate_score = round(candidate_norm * 100, 2)
    score_delta = round(candidate_score - baseline_score, 2)
    detail = (
        f"{spec.title.lower()} comparison: baseline={_format_value(baseline_value)}, "
        f"candidate={_format_value(candidate_value)}, delta={score_delta:+.2f}"
    )
    return EvolutionMetricComparison(
        metric_id=spec.metric_id,
        title=spec.title,
        weight=spec.weight,
        status=EVOLUTION_METRIC_STATUS_SCORED,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        score_delta=score_delta,
        detail=detail,
    )


def _coerce_float(value: object | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clamp_fraction(value: float | None) -> float | None:
    if value is None:
        return None
    return min(max(value, 0.0), 1.0)


def _normalize_conformance_score(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    status = normalize_conformance_status(str(value))
    if status == CONFORMANCE_GREEN:
        return 1.0
    if status == CONFORMANCE_YELLOW:
        return 0.5
    if status == CONFORMANCE_RED:
        return 0.0
    return None


def _normalize_inverse_count(value: object | None) -> float | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return 1.0 / (1.0 + max(number, 0.0))


def _normalize_runtime_score(value: object | None) -> float | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return 1.0 / (1.0 + (max(number, 0.0) / 1000.0))


def _normalize_token_score(value: object | None) -> float | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return 1.0 / (1.0 + (max(number, 0.0) / 10000.0))


def _normalize_reviewability_score(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    mapping = {
        "high": 1.0,
        "medium": 0.6,
        "low": 0.3,
        "blocked": 0.0,
    }
    return mapping.get(normalized)


def _format_value(value: object | None) -> str:
    if value in (None, ""):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


_METRIC_SPECS: tuple[_MetricSpec, ...] = (
    _MetricSpec(
        metric_id="verify-pass-rate",
        title="Verify Pass Rate",
        weight=0.35,
        extractor=lambda metrics: metrics.verify_pass_rate,
        normalizer=lambda value: _clamp_fraction(_coerce_float(value)),
    ),
    _MetricSpec(
        metric_id="conformance-status",
        title="Conformance Status",
        weight=0.15,
        extractor=lambda metrics: metrics.conformance_status,
        normalizer=_normalize_conformance_score,
    ),
    _MetricSpec(
        metric_id="drift-count",
        title="Drift Count",
        weight=0.15,
        extractor=lambda metrics: metrics.drift_count,
        normalizer=_normalize_inverse_count,
    ),
    _MetricSpec(
        metric_id="unresolved-warnings",
        title="Unresolved Warnings",
        weight=0.15,
        extractor=lambda metrics: metrics.unresolved_warning_count,
        normalizer=_normalize_inverse_count,
    ),
    _MetricSpec(
        metric_id="runtime-ms",
        title="Runtime",
        weight=0.10,
        extractor=lambda metrics: metrics.runtime_ms,
        normalizer=_normalize_runtime_score,
    ),
    _MetricSpec(
        metric_id="token-estimate",
        title="Token Estimate",
        weight=0.05,
        extractor=lambda metrics: metrics.token_estimate,
        normalizer=_normalize_token_score,
    ),
    _MetricSpec(
        metric_id="operator-reviewability",
        title="Operator Reviewability",
        weight=0.05,
        extractor=lambda metrics: metrics.operator_reviewability,
        normalizer=_normalize_reviewability_score,
    ),
)
