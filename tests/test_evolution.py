from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import sys
import json
from types import SimpleNamespace
from typing import get_args
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.evolution import (
    EVOLUTION_ALL_RUN_STAGES,
    EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT,
    EVOLUTION_ARTIFACT_KIND_REPORT,
    EVOLUTION_ARTIFACT_KIND_RUN_SPEC,
    EVOLUTION_ARTIFACT_KIND_VERIFICATION,
    EVOLUTION_ARTIFACT_OWNER_EVOLUTION,
    EVOLUTION_ARTIFACT_OWNER_SISYPHUS,
    EVOLUTION_ARTIFACT_STATUS_FUTURE,
    EVOLUTION_ARTIFACT_STATUS_PLANNED,
    EVOLUTION_ARTIFACT_STATUS_RECORDED,
    EVOLUTION_DEFAULT_REVIEW_GATES,
    EVOLUTION_ENVELOPE_STATUS_INVALIDATION,
    EVOLUTION_ENVELOPE_STATUS_PROMOTION,
    EVOLUTION_EVENT_DECISION_RECORDED,
    EVOLUTION_EVENT_EXECUTION_PROJECTED,
    EVOLUTION_EVENT_FOLLOWUP_REQUESTED,
    EVOLUTION_EVENT_RUN_FAILED,
    EVOLUTION_EVENT_RUN_RECORDED,
    EVOLUTION_EVENT_VERIFICATION_PROJECTED,
    EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK,
    EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
    EVOLUTION_EVALUATION_STATUS_COMPLETED,
    EVOLUTION_EVALUATION_STATUS_FAILED,
    EVOLUTION_EVALUATION_STATUS_PLANNED,
    EVOLUTION_EXTENSION_STAGE_SEQUENCE,
    EVOLUTION_FAILURE_SHAPE,
    EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND,
    EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST,
    EVOLUTION_INVALIDATION_ACTION_REPROJECT_RECEIPTS,
    EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
    EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
    EVOLUTION_INVALIDATION_CHANGE_ENVELOPE,
    EVOLUTION_INVALIDATION_CHANGE_EXECUTION_RECEIPT,
    EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST,
    EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES,
    EVOLUTION_INVALIDATION_CHANGE_VERIFICATION,
    EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY,
    EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED,
    EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED,
    EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED,
    EVOLUTION_PHASE_1,
    EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
    EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION,
    EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED,
    EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE,
    EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW,
    EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
    EVOLUTION_READ_ONLY_RUN_STAGES,
    EVOLUTION_READ_ONLY_STAGE_SEQUENCE,
    EVOLUTION_STAGE_FAILED,
    EVOLUTION_STAGE_REPORT_BUILT,
    EVOLUTION_TARGET_KIND_TEXT_POLICY,
    EvolutionArtifactRef,
    EvolutionBridgedFollowupTask,
    EvolutionCandidateArtifact,
    EvolutionDatasetArtifact,
    EvolutionDecisionEnvelope,
    EvolutionEvaluationArtifact,
    EvolutionEvaluationExecutionError,
    EvolutionEvaluationOutcome,
    EvolutionEvidenceSummary,
    EvolutionFollowupRequest,
    EvolutionFollowupExecutionProjection,
    EvolutionFollowupVerificationProjection,
    EvolutionFollowupRequestArtifact,
    EvolutionInvalidationChange,
    EvolutionInvalidationOutcome,
    EvolutionMaterializationError,
    EvolutionPlannedMetrics,
    EvolutionPromotionCandidate,
    EvolutionPromotionGateResult,
    EvolutionReportArtifact,
    EvolutionRunExecutionError,
    EvolutionRunRequest,
    EvolutionRunResult,
    EvolutionRunSpec,
    EvolutionRunStage,
    EvolutionStageFailure,
    EvolutionVerificationObligation,
    ExecutionReceiptArtifact,
    PromotionDecisionArtifact,
    VerificationArtifact,
    build_evolution_dataset,
    build_evolution_report,
    bridge_evolution_followup_request,
    build_sisyphus_evaluation_request,
    build_worktree_evaluation_command_plan,
    dedupe_artifact_refs,
    evaluate_evolution_constraints,
    evaluate_evolution_fitness,
    evaluate_evolution_invalidation,
    evaluate_evolution_promotion_gate,
    execute_evolution_harness,
    execute_sisyphus_evaluation,
    execute_worktree_backed_evaluation,
    execute_evolution_run,
    get_evolution_stage_contract,
    get_evolution_target,
    list_evolution_stage_contracts,
    list_evolution_targets,
    materialize_evolution_evaluation,
    ordered_target_source_paths,
    plan_evolution_harness,
    plan_evolution_run,
    project_followup_execution,
    project_followup_execution_record,
    project_followup_request_artifact,
    project_followup_verification,
    project_followup_verification_record,
    request_evolution_followup,
    record_evolution_decision_envelope,
    evaluate_evolution_followup_decision,
)
from sisyphus.evolution.surface import (
    compare_evolution_runs,
    execute_evolution_surface,
    load_evolution_run_artifacts,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from sisyphus.artifacts import TaskRunRef
from sisyphus.config import load_config
from sisyphus.conformance import append_conformance_log
from sisyphus.state import create_task_record, save_task_record
from sisyphus.templates import materialize_task_templates


def _load_repo_events(repo_root: Path) -> list[dict[str, object]]:
    event_path = repo_root / ".planning" / "events.jsonl"
    if not event_path.exists():
        return []
    return [
        json.loads(line)
        for line in event_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class EvolutionCoreTests(unittest.TestCase):
    def test_registry_exposes_expected_phase_1_targets(self) -> None:
        targets = list_evolution_targets()

        self.assertEqual(
            [target.target_id for target in targets],
            [
                "execution-contract-wording",
                "mcp-tool-descriptions",
                "agent-instruction-sections",
                "conformance-summary-wording",
                "review-gate-explanation-text",
            ],
        )
        self.assertTrue(all(target.phase == EVOLUTION_PHASE_1 for target in targets))
        self.assertTrue(all(target.kind == EVOLUTION_TARGET_KIND_TEXT_POLICY for target in targets))
        self.assertTrue(all(target.live_state_safe for target in targets))
        self.assertEqual(get_evolution_target("mcp-tool-descriptions"), targets[1])

    def test_plan_run_uses_default_registry_without_mutating_repo_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            before = sorted(path.relative_to(repo_root).as_posix() for path in repo_root.rglob("*"))

            run = plan_evolution_run(repo_root)

            after = sorted(path.relative_to(repo_root).as_posix() for path in repo_root.rglob("*"))

        self.assertEqual(run.selection_mode, "default")
        self.assertEqual(run.target_ids, tuple(target.target_id for target in list_evolution_targets()))
        self.assertEqual(run.stage, "planned")
        self.assertEqual(run.status, "planned")
        self.assertEqual(run.dataset_status, "not_built")
        self.assertFalse(run.mutates_live_task_state)
        self.assertEqual(run.request.repo_root, str(repo_root.resolve()))
        self.assertEqual(run.request.target_ids, ())
        self.assertEqual(run.request.run_id, run.run_id)
        self.assertEqual(run.request.created_at, run.created_at)
        self.assertEqual(before, after)

    def test_plan_run_preserves_registry_order_for_explicit_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)

            run = plan_evolution_run(
                repo_root,
                target_ids=[
                    "review-gate-explanation-text",
                    "execution-contract-wording",
                    "mcp-tool-descriptions",
                ],
            )

        self.assertEqual(
            run.target_ids,
            (
                "execution-contract-wording",
                "mcp-tool-descriptions",
                "review-gate-explanation-text",
            ),
        )

    def test_plan_run_rejects_unknown_target_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)

            with self.assertRaisesRegex(ValueError, "unknown evolution target ids: missing-target"):
                plan_evolution_run(repo_root, target_ids=["missing-target"])

    def test_stage_contracts_cover_current_slice(self) -> None:
        self.assertEqual(
            EVOLUTION_READ_ONLY_STAGE_SEQUENCE,
            (
                "planned",
                "dataset_built",
                "harness_planned",
                "constraints_evaluated",
                "fitness_evaluated",
                "report_built",
                "failed",
            ),
        )
        self.assertEqual(
            EVOLUTION_EXTENSION_STAGE_SEQUENCE,
            (
                "ready_for_review",
                "followup_requested",
                "promoted",
                "invalidated",
                "rejected",
            ),
        )
        self.assertEqual(EVOLUTION_READ_ONLY_RUN_STAGES[0], "planned")
        self.assertEqual(EVOLUTION_ALL_RUN_STAGES[-1], "rejected")
        self.assertEqual(
            get_args(EvolutionRunStage),
            EVOLUTION_READ_ONLY_STAGE_SEQUENCE + EVOLUTION_EXTENSION_STAGE_SEQUENCE,
        )

        contracts = list_evolution_stage_contracts(include_future=False)
        self.assertEqual(tuple(contract.stage for contract in contracts), EVOLUTION_READ_ONLY_STAGE_SEQUENCE)
        self.assertTrue(all(contract.future_only is False for contract in contracts))
        self.assertEqual(get_evolution_stage_contract("report_built").output_artifact, "EvolutionReport")

        failure = EvolutionStageFailure(
            stage="constraints_evaluated",
            code="missing_metric_values",
            message="constraints are pending because the harness has no executed metrics yet",
            partial_results=("EvolutionHarnessPlan", "EvolutionDataset"),
            recoverable=True,
        )
        self.assertEqual(failure.stage, "constraints_evaluated")
        self.assertEqual(failure.partial_results, ("EvolutionHarnessPlan", "EvolutionDataset"))
        self.assertTrue(failure.recoverable)
        self.assertEqual(get_evolution_stage_contract("failed").failure_shape, EVOLUTION_FAILURE_SHAPE)

    def test_contract_vocabulary_uses_request_and_result_types(self) -> None:
        artifact_ref = EvolutionArtifactRef(
            artifact_id="artifact-report",
            kind=EVOLUTION_ARTIFACT_KIND_REPORT,
            owner=EVOLUTION_ARTIFACT_OWNER_EVOLUTION,
            notes="contract only",
        )
        failure = EvolutionStageFailure(
            stage="failed",
            code="missing_metrics",
            message="comparison metrics are not attached yet",
            recoverable=True,
            partial_results=("report",),
        )
        result = EvolutionRunResult(
            run_id="EVR-123",
            stage="failed",
            summary="read-only planning is complete but execution evidence is still pending",
            artifact_refs=(artifact_ref,),
            failure=failure,
        )
        candidate = EvolutionPromotionCandidate(
            run_id="EVR-123",
            candidate_id="candidate-001",
            claim="improves wording clarity without increasing drift",
            evidence=(artifact_ref,),
        )
        request = EvolutionRunRequest(
            repo_root="/tmp/repo",
            target_ids=("execution-contract-wording",),
            run_id="EVR-123",
            created_at="2026-04-19T00:00:00Z",
            notes="planning-only request",
        )

        self.assertEqual(result.failure, failure)
        self.assertEqual(candidate.status, "planned_only")
        self.assertEqual(request.target_ids, ("execution-contract-wording",))

    def test_artifact_cycle_exposes_minimum_vertical_slice_types(self) -> None:
        run_spec = EvolutionRunSpec(
            artifact_id="artifact-run-spec",
            producing_stage="planned",
            status=EVOLUTION_ARTIFACT_STATUS_PLANNED,
            run_id="EVR-123",
            repo_root="/tmp/repo",
            selection_mode="default",
            target_ids=("execution-contract-wording",),
            notes="planning-only run spec",
        )
        run_ref = EvolutionArtifactRef(
            artifact_id=run_spec.artifact_id,
            kind=run_spec.kind,
            owner=run_spec.owner,
            notes="run spec dependency",
        )
        dataset = EvolutionDatasetArtifact(
            artifact_id="artifact-dataset",
            producing_stage="dataset_built",
            status=EVOLUTION_ARTIFACT_STATUS_PLANNED,
            run_id="EVR-123",
            selected_task_ids=("TF-1", "TF-2"),
            task_count=2,
            event_count=4,
            trace_sources=("task_records", "events"),
            depends_on=(run_ref,),
        )
        candidate = EvolutionCandidateArtifact(
            artifact_id="artifact-candidate",
            producing_stage="harness_planned",
            status=EVOLUTION_ARTIFACT_STATUS_PLANNED,
            run_id="EVR-123",
            candidate_id="candidate-001",
            candidate_role="candidate",
            target_ids=("execution-contract-wording",),
            change_summary=("tighten wording",),
            depends_on=(run_ref,),
        )
        evaluation = EvolutionEvaluationArtifact(
            artifact_id="artifact-evaluation",
            producing_stage="constraints_evaluated",
            status=EVOLUTION_ARTIFACT_STATUS_PLANNED,
            run_id="EVR-123",
            candidate_id="candidate-001",
            evaluation_scope="read_only",
            metric_fields=("verify_pass_rate", "drift_count"),
            summary_lines=("metrics pending",),
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )
        report = EvolutionReportArtifact(
            artifact_id="artifact-report",
            producing_stage="report_built",
            status=EVOLUTION_ARTIFACT_STATUS_PLANNED,
            run_id="EVR-123",
            headline="Reviewable report pending execution evidence",
            recommendation="await_execution",
            comparison_summary=("no executed harness results yet",),
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )
        followup = EvolutionFollowupRequestArtifact(
            artifact_id="artifact-followup",
            producing_stage="ready_for_review",
            status=EVOLUTION_ARTIFACT_STATUS_FUTURE,
            run_id="EVR-123",
            candidate_id="candidate-001",
            title="Request normal Sisyphus follow-up task",
            summary="handoff instead of direct mutation",
            requested_task_type="feature",
            requested_targets=("execution-contract-wording",),
            required_review_gates=("plan_review", "operator_approval", "verify"),
            followup_task_id="TF-123",
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )
        receipt = ExecutionReceiptArtifact(
            artifact_id="artifact-receipt",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_FUTURE,
            run_id="EVR-123",
            task_id="TF-123",
            receipt_kind="task_run",
            receipt_locator=".planning/tasks/TF-123/receipts/task_run.json",
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )
        verification = VerificationArtifact(
            artifact_id="artifact-verification",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_FUTURE,
            run_id="EVR-123",
            claim="follow-up matches the reviewed evolution request",
            verification_method="tests.test_evolution",
            verification_scope="cross",
            result="pending",
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )
        promotion = PromotionDecisionArtifact(
            artifact_id="artifact-promotion",
            producing_stage="ready_for_review",
            status=EVOLUTION_ARTIFACT_STATUS_FUTURE,
            run_id="EVR-123",
            candidate_id="candidate-001",
            decision="pending_followup_execution",
            claim="candidate is eligible for reviewable handoff",
            followup_task_id="TF-123",
            blocker_details=(),
            depends_on=(run_ref,),
            evidence_refs=(run_ref,),
        )

        self.assertEqual(run_spec.kind, EVOLUTION_ARTIFACT_KIND_RUN_SPEC)
        self.assertEqual(run_spec.owner, EVOLUTION_ARTIFACT_OWNER_EVOLUTION)
        self.assertEqual(report.kind, EVOLUTION_ARTIFACT_KIND_REPORT)
        self.assertEqual(followup.owner, EVOLUTION_ARTIFACT_OWNER_EVOLUTION)
        self.assertEqual(receipt.kind, EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT)
        self.assertEqual(receipt.owner, EVOLUTION_ARTIFACT_OWNER_SISYPHUS)
        self.assertEqual(verification.kind, EVOLUTION_ARTIFACT_KIND_VERIFICATION)
        self.assertEqual(promotion.owner, EVOLUTION_ARTIFACT_OWNER_SISYPHUS)
        self.assertFalse(dataset.persisted)
        self.assertEqual(candidate.depends_on[0], run_ref)
        self.assertEqual(evaluation.evidence_refs[0], run_ref)
        self.assertEqual(promotion.followup_task_id, "TF-123")

    def test_followup_request_is_reviewable_request_only(self) -> None:
        request = EvolutionFollowupRequest(
            source_run_id="EVR-1234567890ab",
            candidate_id="candidate-001",
            title="Refine evolution report wording",
            summary="Request a follow-up task to land the reviewed wording change through Sisyphus.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording", "review-gate-explanation-text"),
            instruction_set=(
                "Update the wording in the documented sections only.",
                "Preserve the current review and verify gates.",
            ),
            owned_paths=("docs/architecture.md", "docs/self-evolution-mcp-plan.md"),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="handoff request includes the review context required for operator approval",
                    method="targeted unit test in tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="fitness_delta",
                    summary="candidate improves wording coverage without changing live task state",
                    locator=".planning/evolution/runs/EVR-1234567890ab/report.md",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )

        self.assertEqual(request.target_scope, ("execution-contract-wording", "review-gate-explanation-text"))
        self.assertEqual(request.required_review_gates, EVOLUTION_DEFAULT_REVIEW_GATES)
        self.assertTrue(request.request_only)
        self.assertFalse(request.permits_plan_approval)
        self.assertFalse(request.permits_spec_freeze)
        self.assertFalse(request.permits_execution)
        self.assertFalse(request.permits_promotion)


class EvolutionFollowupBridgeTests(unittest.TestCase):
    def test_bridge_creates_reviewable_task_request_with_lineage(self) -> None:
        request = EvolutionFollowupRequest(
            source_run_id="EVR-1234567890ab",
            candidate_id="candidate-001",
            title="Refine evolution report wording",
            summary="Create a reviewable follow-up for the accepted evolution candidate.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording", "review-gate-explanation-text"),
            instruction_set=(
                "Update the wording in the documented sections only.",
                "Preserve the current review and verify gates.",
            ),
            owned_paths=("docs/architecture.md", "docs/architecture.md", "docs/self-evolution-mcp-plan.md"),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="follow-up request includes review context",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="fitness_delta",
                    summary="candidate improves wording coverage",
                    locator=".planning/evolution/runs/EVR-1234567890ab/report.md",
                ),
                EvolutionEvidenceSummary(
                    kind="fitness_delta",
                    summary="candidate improves wording coverage",
                    locator=".planning/evolution/runs/EVR-1234567890ab/report.md",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )
        captured: dict[str, object] = {}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            captured["repo_root"] = repo_root
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                ok=True,
                task_id="TF-followup-001",
                task={
                    "id": "TF-followup-001",
                    "slug": "refine-evolution-report-wording",
                    "status": "open",
                    "plan_status": "pending_review",
                    "spec_status": "draft",
                    "workflow_phase": "plan_in_review",
                },
                error=None,
            )

        with tempfile.TemporaryDirectory() as tempdir:
            with patch("sisyphus.evolution.bridge.request_task", side_effect=fake_request_task):
                outcome = bridge_evolution_followup_request(Path(tempdir), request)

        self.assertIsInstance(outcome, EvolutionBridgedFollowupTask)
        self.assertEqual(outcome.task_id, "TF-followup-001")
        self.assertEqual(outcome.plan_status, "pending_review")
        self.assertEqual(outcome.spec_status, "draft")
        self.assertEqual(outcome.workflow_phase, "plan_in_review")
        self.assertEqual(
            outcome.owned_paths,
            ("docs/architecture.md", "docs/self-evolution-mcp-plan.md"),
        )
        self.assertEqual(outcome.artifact.requested_targets, request.target_scope)
        self.assertEqual(outcome.artifact.candidate_id, "candidate-001")
        self.assertEqual(outcome.artifact.required_review_gates, EVOLUTION_DEFAULT_REVIEW_GATES)
        self.assertEqual(outcome.artifact.followup_task_id, "TF-followup-001")
        kwargs = captured["kwargs"]
        self.assertEqual(kwargs["auto_run"], False)
        self.assertEqual(kwargs["task_type"], "feature")
        self.assertEqual(
            kwargs["owned_paths"],
            ["docs/architecture.md", "docs/self-evolution-mcp-plan.md"],
        )
        self.assertIsNone(kwargs.get("config"))
        self.assertIn("Do not bypass plan review", kwargs["instruction"])
        source_context = kwargs["source_context"][EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND]
        self.assertEqual(source_context["source_run_id"], "EVR-1234567890ab")
        self.assertEqual(source_context["candidate_id"], "candidate-001")
        self.assertEqual(source_context["required_review_gates"], list(EVOLUTION_DEFAULT_REVIEW_GATES))
        self.assertEqual(len(source_context["evidence_summary"]), 1)
        self.assertEqual(
            source_context["expected_verification_obligations"][0]["claim"],
            "follow-up request includes review context",
        )

    def test_bridge_preserves_explicit_review_gate_order(self) -> None:
        request = EvolutionFollowupRequest(
            source_run_id="EVR-bridge-gates",
            candidate_id="candidate-ordered",
            title="Preserve review gate order",
            summary="Use a narrowed review gate sequence for a follow-up request.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording",),
            instruction_set=(),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="gate order is preserved",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="report",
                    summary="report is ready for operator review",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
            required_review_gates=("operator_approval", "plan_review", "verify"),
        )
        captured: dict[str, object] = {}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                ok=True,
                task_id="TF-followup-ordered",
                task={
                    "id": "TF-followup-ordered",
                    "slug": "preserve-review-gate-order",
                    "status": "open",
                    "plan_status": "pending_review",
                    "spec_status": "draft",
                    "workflow_phase": "plan_in_review",
                },
                error=None,
            )

        with tempfile.TemporaryDirectory() as tempdir:
            with patch("sisyphus.evolution.bridge.request_task", side_effect=fake_request_task):
                bridge_evolution_followup_request(Path(tempdir), request)

        source_context = captured["kwargs"]["source_context"][EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND]
        self.assertEqual(
            source_context["required_review_gates"],
            ["operator_approval", "plan_review", "verify"],
        )
        self.assertEqual(
            captured["kwargs"]["source_context"][EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND]["required_review_gates"],
            ["operator_approval", "plan_review", "verify"],
        )

    def test_bridge_writes_evolution_followup_event(self) -> None:
        request = EvolutionFollowupRequest(
            source_run_id="EVR-bridge-events",
            candidate_id="candidate-events",
            title="Bridge emits event",
            summary="Emit an evolution follow-up event after task creation.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording",),
            instruction_set=(),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="bridge emits event",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="report",
                    summary="report is ready for handoff",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )

        def fake_request_task(repo_root, *, config=None, **kwargs):
            return SimpleNamespace(
                ok=True,
                task_id="TF-followup-event-001",
                task={
                    "id": "TF-followup-event-001",
                    "slug": "bridge-emits-event",
                    "status": "open",
                    "plan_status": "pending_review",
                    "spec_status": "draft",
                    "workflow_phase": "plan_in_review",
                },
                error=None,
            )

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text(
                "[event_bus]\nprovider = \"jsonl\"\n",
                encoding="utf-8",
            )
            config = load_config(repo_root)
            with patch("sisyphus.evolution.bridge.request_task", side_effect=fake_request_task):
                bridge_evolution_followup_request(repo_root, request, config=config)

            evolution_events = [
                event
                for event in _load_repo_events(repo_root)
                if event.get("event_type") == EVOLUTION_EVENT_FOLLOWUP_REQUESTED
            ]

        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-bridge-events")
        self.assertEqual(evolution_events[0]["data"]["candidate_id"], "candidate-events")
        self.assertEqual(evolution_events[0]["data"]["followup_task_id"], "TF-followup-event-001")

    def _build_constraints(self, *, accepted: bool | None, status: str, notes: str) -> SimpleNamespace:
        return SimpleNamespace(
            run_id="EVR-promotion",
            evaluated_at="2026-04-20T00:00:00Z",
            status=status,
            accepted=accepted,
            warning_increase_threshold=0,
            baseline_evaluation_id="EVR-promotion:baseline",
            candidate_evaluation_id="EVR-promotion:candidate",
            blocking_failure_count=0 if accepted else 1,
            pending_guard_count=0 if accepted is not None else 1,
            checks=(),
            notes=notes,
        )

    def _build_fitness(self, *, eligible: bool | None, status: str, notes: str) -> SimpleNamespace:
        return SimpleNamespace(
            run_id="EVR-promotion",
            evaluated_at="2026-04-20T00:00:00Z",
            status=status,
            eligible_for_promotion=eligible,
            comparable_metric_count=2,
            baseline_score=62.0,
            candidate_score=87.0,
            score_delta=25.0,
            comparisons=(),
            notes=notes,
        )


class EvolutionPromotionGateTests(unittest.TestCase):
    def _build_constraints(self, *, accepted: bool | None, status: str, notes: str) -> SimpleNamespace:
        return SimpleNamespace(
            run_id="EVR-promotion",
            evaluated_at="2026-04-20T00:00:00Z",
            status=status,
            accepted=accepted,
            warning_increase_threshold=0,
            baseline_evaluation_id="EVR-promotion:baseline",
            candidate_evaluation_id="EVR-promotion:candidate",
            blocking_failure_count=0 if accepted else 1,
            pending_guard_count=0 if accepted is not None else 1,
            checks=(),
            notes=notes,
        )

    def _build_fitness(self, *, eligible: bool | None, status: str, notes: str) -> SimpleNamespace:
        return SimpleNamespace(
            run_id="EVR-promotion",
            evaluated_at="2026-04-20T00:00:00Z",
            status=status,
            eligible_for_promotion=eligible,
            comparable_metric_count=2,
            baseline_score=62.0,
            candidate_score=87.0,
            score_delta=25.0,
            comparisons=(),
            notes=notes,
        )

    def _build_followup_artifact(
        self,
        *,
        required_review_gates: tuple[str, ...] = ("plan_review", "operator_approval", "verify"),
    ) -> EvolutionFollowupRequestArtifact:
        return EvolutionFollowupRequestArtifact(
            artifact_id="artifact-followup-promotion",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id="EVR-promotion",
            candidate_id="candidate-123",
            title="Request promotion-gated follow-up",
            summary="Use Sisyphus review gates before any promotion record is written.",
            requested_task_type="feature",
            requested_targets=("execution-contract-wording",),
            required_review_gates=required_review_gates,
            followup_task_id="TF-promotion-001",
        )

    def _build_execution_projection(self) -> EvolutionFollowupExecutionProjection:
        receipt = ExecutionReceiptArtifact(
            artifact_id="artifact-followup-receipt-1",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id="EVR-promotion",
            task_id="TF-promotion-001",
            receipt_kind="verify_command_1",
            receipt_locator=".planning/tasks/TF-promotion-001/VERIFY.md",
        )
        return EvolutionFollowupExecutionProjection(
            source_run_id="EVR-promotion",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            execution_receipts=(receipt,),
            task_runs=(
                TaskRunRef(
                    task_id="TF-promotion-001",
                    run_id="TF-promotion-001:verify:1",
                    status="passed",
                    receipt_locator=receipt.artifact_id,
                ),
            ),
        )

    def _build_verification_projection(
        self,
        execution_projection: EvolutionFollowupExecutionProjection,
        *,
        result: str = "passed",
    ) -> EvolutionFollowupVerificationProjection:
        artifact = VerificationArtifact(
            artifact_id="artifact-followup-verification-1",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id="EVR-promotion",
            claim="follow-up execution remains reviewable",
            verification_method="tests.test_evolution",
            verification_scope="followup_execution",
            result=result,
            depends_on=tuple(
                receipt.to_ref(notes=receipt.receipt_kind)
                for receipt in execution_projection.execution_receipts
            ),
            evidence_refs=tuple(
                receipt.to_ref(notes=receipt.receipt_kind)
                for receipt in execution_projection.execution_receipts
            ),
        )
        return EvolutionFollowupVerificationProjection(
            source_run_id="EVR-promotion",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            verification_artifacts=(artifact,),
            execution_projection=execution_projection,
        )

    def test_evaluate_promotion_gate_reports_ready_for_review_before_execution_closure(self) -> None:
        followup = self._build_followup_artifact()
        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=True,
                status="accepted",
                notes="candidate satisfies hard guards",
            ),
            fitness=self._build_fitness(
                eligible=True,
                status="scored",
                notes="fitness scoring supports reviewable handoff",
            ),
        )

        self.assertIsInstance(gate, EvolutionPromotionGateResult)
        self.assertEqual(gate.status, EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW)
        self.assertTrue(gate.reviewable_handoff_eligible)
        self.assertFalse(gate.promotion_eligible)
        self.assertEqual(
            [blocker.blocker_id for blocker in gate.blocking_conditions],
            ["execution_receipts_pending", "verification_artifacts_pending"],
        )
        self.assertTrue(all(
            blocker.scope == EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION
            for blocker in gate.blocking_conditions
        ))

    def test_evaluate_promotion_gate_reports_eligible_when_execution_and_verification_pass(self) -> None:
        followup = self._build_followup_artifact()
        execution_projection = self._build_execution_projection()
        verification_projection = self._build_verification_projection(execution_projection)

        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=True,
                status="accepted",
                notes="candidate satisfies hard guards",
            ),
            fitness=self._build_fitness(
                eligible=True,
                status="scored",
                notes="fitness scoring supports promotion",
            ),
            execution_projection=execution_projection,
            verification_projection=verification_projection,
        )

        self.assertEqual(gate.status, EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE)
        self.assertTrue(gate.reviewable_handoff_eligible)
        self.assertTrue(gate.promotion_eligible)
        self.assertEqual(gate.blocking_conditions, ())
        self.assertEqual(
            [ref.kind for ref in gate.evidence_refs],
            [
                followup.kind,
                EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT,
                EVOLUTION_ARTIFACT_KIND_VERIFICATION,
            ],
        )

    def test_evaluate_promotion_gate_blocks_on_missing_review_gates_and_ineligible_fitness(self) -> None:
        followup = self._build_followup_artifact(required_review_gates=())

        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=False,
                status="rejected",
                notes="hard guards failed",
            ),
            fitness=self._build_fitness(
                eligible=False,
                status="rejected",
                notes="fitness result is not promotion-eligible",
            ),
        )

        self.assertEqual(gate.status, EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED)
        self.assertFalse(gate.reviewable_handoff_eligible)
        self.assertFalse(gate.promotion_eligible)
        blocker_scopes = {blocker.blocker_id: blocker.scope for blocker in gate.blocking_conditions}
        self.assertEqual(blocker_scopes["review_gates_missing"], EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF)
        self.assertEqual(blocker_scopes["constraints_rejected"], EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF)
        self.assertEqual(blocker_scopes["fitness_rejected"], EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF)

    def test_evaluate_promotion_gate_rejects_mismatched_execution_lineage(self) -> None:
        followup = self._build_followup_artifact()
        execution_projection = EvolutionFollowupExecutionProjection(
            source_run_id="EVR-other",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            execution_receipts=(),
            task_runs=(),
        )

        with self.assertRaisesRegex(ValueError, "execution projection run_id"):
            evaluate_evolution_promotion_gate(
                followup,
                constraints=self._build_constraints(
                    accepted=True,
                    status="accepted",
                    notes="candidate satisfies hard guards",
                ),
                fitness=self._build_fitness(
                    eligible=True,
                    status="scored",
                    notes="fitness scoring supports promotion",
                ),
                execution_projection=execution_projection,
            )

    def test_record_decision_envelope_records_promotion_artifact_for_eligible_gate(self) -> None:
        followup = self._build_followup_artifact()
        execution_projection = self._build_execution_projection()
        verification_projection = self._build_verification_projection(execution_projection)
        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=True,
                status="accepted",
                notes="candidate satisfies hard guards",
            ),
            fitness=self._build_fitness(
                eligible=True,
                status="scored",
                notes="fitness scoring supports promotion",
            ),
            execution_projection=execution_projection,
            verification_projection=verification_projection,
        )

        envelope = record_evolution_decision_envelope(
            gate,
            claim="candidate is fully promotion-eligible",
        )

        self.assertIsInstance(envelope, EvolutionDecisionEnvelope)
        self.assertEqual(envelope.status, EVOLUTION_ENVELOPE_STATUS_PROMOTION)
        self.assertIsNotNone(envelope.promotion_decision)
        self.assertIsNone(envelope.invalidation_record)
        self.assertEqual(envelope.promotion_decision.decision, EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE)
        self.assertEqual(envelope.promotion_decision.candidate_id, "candidate-123")
        self.assertEqual(envelope.promotion_decision.followup_task_id, "TF-promotion-001")
        self.assertEqual(
            envelope.promotion_decision.evidence_refs,
            gate.evidence_refs,
        )

    def test_record_decision_envelope_records_ready_for_review_as_promotion_decision(self) -> None:
        followup = self._build_followup_artifact()
        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=True,
                status="accepted",
                notes="candidate satisfies hard guards",
            ),
            fitness=self._build_fitness(
                eligible=True,
                status="scored",
                notes="fitness scoring supports reviewable handoff",
            ),
        )

        envelope = record_evolution_decision_envelope(
            gate,
            claim="candidate is ready for reviewable handoff",
        )

        self.assertEqual(envelope.status, EVOLUTION_ENVELOPE_STATUS_PROMOTION)
        self.assertEqual(
            envelope.promotion_decision.decision,
            EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW,
        )
        self.assertEqual(len(envelope.promotion_decision.blocker_details), 2)

    def test_record_decision_envelope_records_blocked_gate_as_invalidation(self) -> None:
        followup = self._build_followup_artifact(required_review_gates=())
        gate = evaluate_evolution_promotion_gate(
            followup,
            constraints=self._build_constraints(
                accepted=False,
                status="rejected",
                notes="hard guards failed",
            ),
            fitness=self._build_fitness(
                eligible=False,
                status="rejected",
                notes="fitness result is not promotion-eligible",
            ),
        )

        envelope = record_evolution_decision_envelope(
            gate,
            claim="candidate cannot progress because obligations are incomplete",
        )

        self.assertEqual(envelope.status, EVOLUTION_ENVELOPE_STATUS_INVALIDATION)
        self.assertIsNone(envelope.promotion_decision)
        self.assertEqual(envelope.invalidation_record.status, EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED)
        self.assertEqual(envelope.invalidation_record.candidate_id, "candidate-123")
        self.assertEqual(
            envelope.invalidation_record.followup_task_id,
            "TF-promotion-001",
        )
        self.assertGreaterEqual(len(envelope.invalidation_record.blocker_details), 3)

    def test_record_decision_envelope_dedupes_evidence_refs(self) -> None:
        gate = EvolutionPromotionGateResult(
            run_id="EVR-promotion",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            status=EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW,
            reviewable_handoff_eligible=True,
            promotion_eligible=False,
            required_review_gates=("plan_review",),
            blocking_conditions=(),
            evidence_refs=(
                EvolutionArtifactRef(
                    artifact_id="artifact-a",
                    kind="report",
                    owner=EVOLUTION_ARTIFACT_OWNER_EVOLUTION,
                    notes="same",
                ),
                EvolutionArtifactRef(
                    artifact_id="artifact-a",
                    kind="report",
                    owner=EVOLUTION_ARTIFACT_OWNER_EVOLUTION,
                    notes="same",
                ),
            ),
            notes="ready for review",
        )

        envelope = record_evolution_decision_envelope(
            gate,
            claim="dedupe evidence refs",
        )

        self.assertEqual(len(envelope.evidence_refs), 1)
        self.assertEqual(len(envelope.promotion_decision.evidence_refs), 1)

    def test_record_decision_envelope_writes_evolution_decision_event(self) -> None:
        gate = EvolutionPromotionGateResult(
            run_id="EVR-promotion",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            status=EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW,
            reviewable_handoff_eligible=True,
            promotion_eligible=False,
            required_review_gates=("plan_review",),
            blocking_conditions=(),
            evidence_refs=(),
            notes="ready for review",
        )

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text(
                "[event_bus]\nprovider = \"jsonl\"\n",
                encoding="utf-8",
            )
            config = load_config(repo_root)

            envelope = record_evolution_decision_envelope(
                gate,
                claim="emit decision event",
                repo_root=repo_root,
                config=config,
            )

            evolution_events = [
                event
                for event in _load_repo_events(repo_root)
                if event.get("event_type") == EVOLUTION_EVENT_DECISION_RECORDED
            ]

        self.assertEqual(envelope.status, EVOLUTION_ENVELOPE_STATUS_PROMOTION)
        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-promotion")
        self.assertEqual(evolution_events[0]["data"]["envelope_status"], EVOLUTION_ENVELOPE_STATUS_PROMOTION)

    def test_record_decision_envelope_rejects_unsupported_status(self) -> None:
        gate = EvolutionPromotionGateResult(
            run_id="EVR-promotion",
            candidate_id="candidate-123",
            followup_task_id="TF-promotion-001",
            status="unexpected",
            reviewable_handoff_eligible=False,
            promotion_eligible=False,
            required_review_gates=(),
            blocking_conditions=(),
            evidence_refs=(),
            notes="unexpected status",
        )

        with self.assertRaisesRegex(ValueError, "unsupported promotion gate status"):
            record_evolution_decision_envelope(
                gate,
                claim="should fail",
            )

    def test_bridge_rejects_privileged_permission_flags(self) -> None:
        base_request = EvolutionFollowupRequest(
            source_run_id="EVR-prohibited",
            candidate_id="candidate-prohibited",
            title="Reject privileged bridge",
            summary="This request should fail before a task is created.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording",),
            instruction_set=(),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="request-only bridge rejects privileged flags",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="report",
                    summary="operator review is still required",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )
        for field_name in (
            "permits_plan_approval",
            "permits_spec_freeze",
            "permits_execution",
            "permits_promotion",
        ):
            with self.subTest(field_name=field_name):
                request = replace(base_request, **{field_name: True})
                with tempfile.TemporaryDirectory() as tempdir:
                    with self.assertRaisesRegex(ValueError, field_name):
                        bridge_evolution_followup_request(Path(tempdir), request)

    def test_bridge_requires_evidence_and_verification_obligations(self) -> None:
        request = EvolutionFollowupRequest(
            source_run_id="EVR-missing",
            candidate_id="candidate-missing",
            title="Reject underspecified bridge",
            summary="The bridge should fail loudly on missing evidence.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording",),
            instruction_set=(),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(),
            evidence_summary=(),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaisesRegex(ValueError, "verification obligations"):
                bridge_evolution_followup_request(Path(tempdir), request)


class EvolutionInvalidationRuleTests(unittest.TestCase):
    def _build_followup_artifact(self) -> EvolutionFollowupRequestArtifact:
        return EvolutionFollowupRequestArtifact(
            artifact_id="artifact-followup-invalidation",
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id="EVR-invalidation",
            candidate_id="candidate-invalidation",
            title="Reproject invalidated follow-up state",
            summary="Invalidate derived promotion state when upstream artifacts change.",
            requested_task_type="feature",
            requested_targets=("execution-contract-wording",),
            required_review_gates=("plan_review", "operator_approval", "verify"),
            followup_task_id="TF-invalidation-001",
        )

    def test_followup_request_change_recreates_followup_and_reruns_gate(self) -> None:
        followup = self._build_followup_artifact()

        outcome = evaluate_evolution_invalidation(
            followup,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST,
                    detail="follow-up request summary changed after operator review",
                ),
            ),
        )

        self.assertIsInstance(outcome, EvolutionInvalidationOutcome)
        self.assertEqual(outcome.run_id, "EVR-invalidation")
        self.assertEqual(outcome.candidate_id, "candidate-invalidation")
        self.assertEqual(
            outcome.remediation_actions,
            (
                EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST,
                EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
                EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
            ),
        )
        self.assertEqual(
            outcome.stale_artifact_refs,
            (
                followup.to_ref(notes=EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST),
            ),
        )

    def test_execution_receipt_change_reprojects_receipts_and_verification(self) -> None:
        followup = self._build_followup_artifact()
        receipt_ref = EvolutionArtifactRef(
            artifact_id="artifact-receipt-1",
            kind=EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT,
            owner=EVOLUTION_ARTIFACT_OWNER_SISYPHUS,
            notes="verify_command_1",
        )

        outcome = evaluate_evolution_invalidation(
            followup,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_EXECUTION_RECEIPT,
                    detail="verify receipt changed after rerun",
                    stale_artifact_refs=(receipt_ref,),
                ),
            ),
        )

        self.assertEqual(
            outcome.remediation_actions,
            (
                EVOLUTION_INVALIDATION_ACTION_REPROJECT_RECEIPTS,
                EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
                EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
                EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
            ),
        )
        self.assertEqual(outcome.stale_artifact_refs, (receipt_ref,))

    def test_combined_changes_dedupe_actions_and_stale_refs(self) -> None:
        followup = self._build_followup_artifact()
        verification_ref = EvolutionArtifactRef(
            artifact_id="artifact-verification-1",
            kind=EVOLUTION_ARTIFACT_KIND_VERIFICATION,
            owner=EVOLUTION_ARTIFACT_OWNER_SISYPHUS,
            notes="passed",
        )
        envelope_ref = EvolutionArtifactRef(
            artifact_id="artifact-envelope-1",
            kind="promotion_decision",
            owner=EVOLUTION_ARTIFACT_OWNER_SISYPHUS,
            notes="ready_for_review",
        )

        outcome = evaluate_evolution_invalidation(
            followup,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_VERIFICATION,
                    detail="verification evidence changed",
                    stale_artifact_refs=(verification_ref, verification_ref),
                ),
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_ENVELOPE,
                    detail="decision envelope must be rerecorded",
                    stale_artifact_refs=(envelope_ref,),
                ),
            ),
        )

        self.assertEqual(
            outcome.remediation_actions,
            (
                EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
                EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
                EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
            ),
        )
        self.assertEqual(
            outcome.stale_artifact_refs,
            dedupe_artifact_refs((verification_ref, verification_ref, envelope_ref)),
        )

    def test_review_gate_change_preserves_identity_and_marks_followup_stale(self) -> None:
        followup = self._build_followup_artifact()
        review_gate_ref = EvolutionArtifactRef(
            artifact_id="artifact-review-gates",
            kind=followup.kind,
            owner=followup.owner,
            notes="review_gate_snapshot",
        )

        outcome = evaluate_evolution_invalidation(
            followup,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES,
                    detail="required review gates changed after policy update",
                    stale_artifact_refs=(review_gate_ref,),
                ),
            ),
        )

        self.assertEqual(outcome.run_id, followup.run_id)
        self.assertEqual(outcome.candidate_id, followup.candidate_id)
        self.assertEqual(outcome.followup_task_id, followup.followup_task_id)
        self.assertEqual(
            outcome.stale_artifact_refs,
            dedupe_artifact_refs(
                (
                    followup.to_ref(notes=EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES),
                    review_gate_ref,
                )
            ),
        )

    def test_unsupported_change_kind_fails_loudly(self) -> None:
        followup = self._build_followup_artifact()

        with self.assertRaisesRegex(ValueError, "unsupported evolution invalidation change kind"):
            evaluate_evolution_invalidation(
                followup,
                changes=(
                    EvolutionInvalidationChange(
                        change_kind="unknown_change",
                        detail="should fail",
                    ),
                ),
            )

    def test_empty_change_set_fails_loudly(self) -> None:
        followup = self._build_followup_artifact()

        with self.assertRaisesRegex(ValueError, "requires at least one change"):
            evaluate_evolution_invalidation(followup, changes=())


class EvolutionFollowupReceiptProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _configure_followup_task(
        self,
        task: dict,
        *,
        verify_results: list[dict] | None,
        include_promotion_receipt: bool = False,
        extra_source_context: dict[str, object] | None = None,
    ) -> tuple[dict, Path]:
        task_dir = self.repo_root / task["task_dir"]
        task.setdefault("meta", {})
        source_context: dict[str, object] = dict(extra_source_context or {})
        source_context[EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND] = {
            "source_run_id": "EVR-followup-receipts",
            "candidate_id": "candidate-007",
            "promotion_intent": EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
            "target_scope": ["execution-contract-wording"],
            "required_review_gates": list(EVOLUTION_DEFAULT_REVIEW_GATES),
            "request_only": True,
            "expected_verification_obligations": [
                {
                    "claim": "follow-up execution remains reviewable",
                    "method": "tests.test_evolution",
                    "required": True,
                }
            ],
            "evidence_summary": [
                {
                    "kind": "report",
                    "summary": "candidate approved for follow-up execution",
                    "locator": ".planning/evolution/runs/EVR-followup-receipts/report.md",
                }
            ],
        }
        task["meta"]["source_context"] = source_context
        task["last_verify_results"] = verify_results or []
        task["verify_status"] = "passed" if verify_results else "not_run"
        if include_promotion_receipt:
            promotion_relative = task["docs"]["promotion"]
            promotion_path = task_dir / promotion_relative
            promotion_path.parent.mkdir(parents=True, exist_ok=True)
            promotion_path.write_text("{\"recorded\": true}\n", encoding="utf-8")
            task["promotion"] = {
                "required": True,
                "status": "promotion_recorded",
                "strategy": "direct",
                "receipt_path": promotion_relative,
            }
        save_task_record(task_dir / "task.json", task)
        return task, task_dir

    def test_project_followup_execution_builds_task_runs_and_verify_receipts(self) -> None:
        task = self._new_task("followup-receipts")
        task, task_dir = self._configure_followup_task(
            task,
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                },
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "failed",
                    "exit_code": 1,
                    "started_at": "2026-04-20T00:01:00Z",
                    "finished_at": "2026-04-20T00:01:01Z",
                    "output_excerpt": "boom",
                },
            ],
            extra_source_context={"unrelated": {"value": 1}},
        )

        projection = project_followup_execution(
            self.repo_root,
            self.config,
            task["id"],
        )

        self.assertIsInstance(projection, EvolutionFollowupExecutionProjection)
        self.assertEqual(projection.source_run_id, "EVR-followup-receipts")
        self.assertEqual(projection.candidate_id, "candidate-007")
        self.assertEqual(projection.followup_task_id, task["id"])
        self.assertEqual(len(projection.execution_receipts), 2)
        self.assertEqual(len(projection.task_runs), 2)
        self.assertEqual(projection.task_runs[0].run_id, f"{task['id']}:verify:1")
        self.assertEqual(projection.task_runs[1].status, "failed")
        self.assertEqual(
            projection.task_runs[0].receipt_locator,
            projection.execution_receipts[0].artifact_id,
        )
        self.assertEqual(
            projection.execution_receipts[0].receipt_locator,
            (Path(task["task_dir"]) / task["docs"]["verify"]).as_posix(),
        )
        self.assertEqual(projection.execution_receipts[0].receipt_kind, "verify_command_1")
        self.assertEqual(projection.execution_receipts[1].receipt_kind, "verify_command_2")
        self.assertTrue((task_dir / task["docs"]["verify"]).exists())
        evolution_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_EXECUTION_PROJECTED
        ]
        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-followup-receipts")
        self.assertEqual(evolution_events[0]["data"]["receipt_count"], 2)

    def test_project_followup_execution_includes_optional_promotion_receipt(self) -> None:
        task = self._new_task("followup-promotion-receipt")
        task, _ = self._configure_followup_task(
            task,
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
            include_promotion_receipt=True,
        )

        projection = project_followup_execution_record(
            task=task,
            task_dir=self.repo_root / task["task_dir"],
        )

        self.assertEqual(len(projection.task_runs), 1)
        self.assertEqual(len(projection.execution_receipts), 2)
        self.assertEqual(projection.execution_receipts[-1].receipt_kind, "promotion_receipt")
        self.assertEqual(
            projection.execution_receipts[-1].receipt_locator,
            (Path(task["task_dir"]) / task["docs"]["promotion"]).as_posix(),
        )

    def test_project_followup_execution_reads_first_class_promotion_bundle(self) -> None:
        task = self._new_task("followup-promotion-bundle")
        task, task_dir = self._configure_followup_task(
            task,
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
        )
        promotion_relative = task["docs"]["promotion"]
        promotion_path = task_dir / promotion_relative
        promotion_path.parent.mkdir(parents=True, exist_ok=True)
        promotion_path.write_text("{\"recorded\": true}\n", encoding="utf-8")
        task["promotion"] = {
            "required": True,
            "status": "promotion_recorded",
            "strategy": "direct",
            "receipt_path": promotion_relative,
        }
        task.get("meta", {}).pop("promotion", None)
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        projection = project_followup_execution_record(
            task=task,
            task_dir=self.repo_root / task["task_dir"],
        )

        self.assertEqual(projection.execution_receipts[-1].receipt_kind, "promotion_receipt")
        self.assertEqual(
            projection.execution_receipts[-1].receipt_locator,
            (Path(task["task_dir"]) / promotion_relative).as_posix(),
        )

    def test_project_followup_execution_rejects_missing_verify_results(self) -> None:
        task = self._new_task("followup-no-verify-results")
        task, _ = self._configure_followup_task(task, verify_results=[])

        with self.assertRaisesRegex(ValueError, "no verify results"):
            project_followup_execution_record(
                task=task,
                task_dir=self.repo_root / task["task_dir"],
            )

    def test_project_followup_execution_rejects_missing_promotion_receipt_file(self) -> None:
        task = self._new_task("followup-missing-promotion-receipt")
        task, _ = self._configure_followup_task(
            task,
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
        )
        task["promotion"] = {
            "required": True,
            "status": "promotion_recorded",
            "strategy": "direct",
            "receipt_path": task["docs"]["promotion"],
        }
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        with self.assertRaisesRegex(FileNotFoundError, "promotion receipt"):
            project_followup_execution_record(
                task=task,
                task_dir=self.repo_root / task["task_dir"],
            )


class EvolutionFollowupVerificationProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _configure_followup_task(
        self,
        task: dict,
        *,
        verify_status: str,
        verify_results: list[dict],
        obligations: list[dict] | None = None,
        extra_source_context: dict[str, object] | None = None,
    ) -> tuple[dict, Path]:
        task_dir = self.repo_root / task["task_dir"]
        task.setdefault("meta", {})
        source_context: dict[str, object] = dict(extra_source_context or {})
        source_context[EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND] = {
            "source_run_id": "EVR-followup-verification",
            "candidate_id": "candidate-011",
            "promotion_intent": EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
            "target_scope": ["execution-contract-wording"],
            "required_review_gates": list(EVOLUTION_DEFAULT_REVIEW_GATES),
            "request_only": True,
            "expected_verification_obligations": obligations
            if obligations is not None
            else [
                {
                    "claim": "follow-up execution remains reviewable",
                    "method": "tests.test_evolution",
                    "required": True,
                },
                {
                    "claim": "linked receipts prove the verification path",
                    "method": "manual receipt projection",
                    "required": True,
                },
            ],
            "evidence_summary": [
                {
                    "kind": "report",
                    "summary": "candidate approved for receipt-backed verification",
                    "locator": ".planning/evolution/runs/EVR-followup-verification/report.md",
                }
            ],
        }
        task["meta"]["source_context"] = source_context
        task["verify_status"] = verify_status
        task["last_verify_results"] = verify_results
        save_task_record(task_dir / "task.json", task)
        return task, task_dir

    def test_project_followup_verification_preserves_claim_method_and_receipt_evidence(self) -> None:
        task = self._new_task("followup-verification-pass")
        task, _ = self._configure_followup_task(
            task,
            verify_status="passed",
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
            extra_source_context={"unrelated": {"ignored": True}},
        )

        projection = project_followup_verification(
            self.repo_root,
            self.config,
            task["id"],
        )

        self.assertIsInstance(projection, EvolutionFollowupVerificationProjection)
        self.assertEqual(projection.source_run_id, "EVR-followup-verification")
        self.assertEqual(projection.candidate_id, "candidate-011")
        self.assertEqual(projection.followup_task_id, task["id"])
        self.assertEqual(len(projection.verification_artifacts), 2)
        self.assertEqual(
            projection.verification_artifacts[0].artifact_id,
            f"artifact-{task['id']}-followup-verification-1",
        )
        self.assertEqual(
            projection.verification_artifacts[0].claim,
            "follow-up execution remains reviewable",
        )
        self.assertEqual(
            projection.verification_artifacts[0].verification_method,
            "tests.test_evolution",
        )
        self.assertEqual(projection.verification_artifacts[0].result, "passed")
        self.assertEqual(
            projection.verification_artifacts[0].evidence_refs,
            tuple(
                receipt.to_ref(notes=receipt.receipt_kind)
                for receipt in projection.execution_projection.execution_receipts
            ),
        )
        self.assertEqual(
            projection.verification_artifacts[0].depends_on,
            projection.verification_artifacts[0].evidence_refs,
        )
        evolution_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_VERIFICATION_PROJECTED
        ]
        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-followup-verification")
        self.assertEqual(evolution_events[0]["data"]["verification_count"], 2)

    def test_project_followup_verification_marks_failed_execution_as_failed(self) -> None:
        task = self._new_task("followup-verification-failed")
        task, task_dir = self._configure_followup_task(
            task,
            verify_status="failed",
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "failed",
                    "exit_code": 1,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "boom",
                }
            ],
        )

        projection = project_followup_verification_record(
            task=task,
            task_dir=task_dir,
        )

        self.assertTrue(all(artifact.result == "failed" for artifact in projection.verification_artifacts))

    def test_project_followup_verification_rejects_missing_obligations(self) -> None:
        task = self._new_task("followup-verification-no-obligations")
        task, task_dir = self._configure_followup_task(
            task,
            verify_status="passed",
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
            obligations=[],
        )

        with self.assertRaisesRegex(ValueError, "no verification obligations"):
            project_followup_verification_record(
                task=task,
                task_dir=task_dir,
            )

    def test_project_followup_verification_surfaces_missing_receipt_linkage(self) -> None:
        task = self._new_task("followup-verification-missing-receipt")
        task, task_dir = self._configure_followup_task(
            task,
            verify_status="passed",
            verify_results=[
                {
                    "command": "python -m unittest -q tests.test_evolution",
                    "status": "passed",
                    "exit_code": 0,
                    "started_at": "2026-04-20T00:00:00Z",
                    "finished_at": "2026-04-20T00:00:01Z",
                    "output_excerpt": "ok",
                }
            ],
        )
        verify_path = task_dir / task["docs"]["verify"]
        verify_path.unlink()

        with self.assertRaisesRegex(FileNotFoundError, "verify receipt document"):
            project_followup_verification_record(
                task=task,
                task_dir=task_dir,
            )


class EvolutionOperatorSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _write_evolution_run(
        self,
        run_id: str,
        *,
        target_ids: tuple[str, ...] = ("execution-contract-wording",),
        score_delta: float = 0.25,
    ) -> Path:
        artifact_dir = self.repo_root / ".planning" / "evolution" / "runs" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "run.json").write_text(
            json.dumps(
                {
                    "run": {
                        "run_id": run_id,
                        "repo_root": str(self.repo_root),
                        "target_ids": list(target_ids),
                        "selection_mode": "explicit",
                        "status": "planned",
                        "stage": "planned",
                    },
                    "artifact_dir": str(artifact_dir),
                    "entrypoint": "execute_evolution_run",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "dataset.json").write_text(
            json.dumps(
                {
                    "repo_root": str(self.repo_root),
                    "generated_at": "2026-04-20T00:00:00Z",
                    "event_log_path": str(self.repo_root / ".planning" / "events.jsonl"),
                    "selected_task_ids": [f"{run_id}-task-1"],
                    "task_traces": [],
                    "event_traces": [],
                    "task_count": 1,
                    "event_count": 1,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "harness_plan.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "repo_root": str(self.repo_root),
                    "created_at": "2026-04-20T00:00:00Z",
                    "dataset_task_ids": [f"{run_id}-task-1"],
                    "dataset_event_count": 1,
                    "baseline": {"evaluation_id": f"{run_id}:baseline", "role": "baseline"},
                    "candidate": {"evaluation_id": f"{run_id}:candidate", "role": "candidate"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "constraints.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": "accepted",
                    "accepted": True,
                    "blocking_failure_count": 0,
                    "pending_guard_count": 0,
                    "checks": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "fitness.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": "scored",
                    "eligible_for_promotion": True,
                    "comparable_metric_count": 1,
                    "baseline_score": 0.62,
                    "candidate_score": 0.62 + score_delta,
                    "score_delta": score_delta,
                    "comparisons": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "report.md").write_text(
            "\n".join(
                [
                    "# Evolution Report",
                    "",
                    f"- Run ID: `{run_id}`",
                    "- Status: `ready_for_review`",
                    "- Recommendation: `review_candidate`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return artifact_dir

    def _fake_request_task_factory(self, captured: dict[str, dict]) -> object:
        def fake_request_task(repo_root, *, config=None, **kwargs):
            task = create_task_record(
                repo_root=repo_root,
                config=config or self.config,
                task_type=kwargs["task_type"],
                slug=kwargs["slug"],
            )
            materialize_task_templates(task)
            task.setdefault("meta", {})["source_context"] = kwargs["source_context"]
            save_task_record(self.repo_root / task["task_dir"] / "task.json", task)
            captured["task"] = task
            return SimpleNamespace(ok=True, task_id=task["id"], task=task, error=None)

        return fake_request_task

    def _configure_followup_results(self, task: dict, *, verify_status: str = "passed") -> None:
        task_dir = self.repo_root / task["task_dir"]
        task["verify_status"] = verify_status
        task["last_verify_results"] = [
            {
                "command": "python -m unittest -q tests.test_evolution",
                "status": verify_status,
                "exit_code": 0 if verify_status == "passed" else 1,
                "started_at": "2026-04-20T00:00:00Z",
                "finished_at": "2026-04-20T00:00:01Z",
                "output_excerpt": "ok" if verify_status == "passed" else "boom",
            }
        ]
        promotion_relative = task["docs"]["promotion"]
        promotion_path = task_dir / promotion_relative
        promotion_path.parent.mkdir(parents=True, exist_ok=True)
        promotion_path.write_text("{\"recorded\": true}\n", encoding="utf-8")
        task.setdefault("meta", {})["promotion"] = {"receipt_path": promotion_relative}
        save_task_record(task_dir / "task.json", task)

    def test_request_evolution_followup_defaults_lineage_metadata(self) -> None:
        self._write_evolution_run("EVR-operator-defaults")
        captured: dict[str, dict] = {}

        with patch(
            "sisyphus.evolution.bridge.request_task",
            side_effect=self._fake_request_task_factory(captured),
        ):
            result = request_evolution_followup(
                self.repo_root,
                run_id="EVR-operator-defaults",
                candidate_id="candidate-001",
                title="Review requested candidate",
                summary="Create a review-gated follow-up task.",
                config=self.config,
            )

        task = captured["task"]
        followup_context = task["meta"]["source_context"][EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND]
        reconstructed = project_followup_request_artifact(task)

        self.assertEqual(result.task_id, task["id"])
        self.assertEqual(result.requested_targets, ("execution-contract-wording",))
        self.assertEqual(result.required_review_gates, EVOLUTION_DEFAULT_REVIEW_GATES)
        self.assertEqual(
            followup_context["expected_verification_obligations"][0]["method"],
            "sisyphus verify",
        )
        self.assertEqual(
            followup_context["evidence_summary"][0]["locator"],
            ".planning/evolution/runs/EVR-operator-defaults/report.md",
        )
        self.assertEqual(reconstructed.run_id, "EVR-operator-defaults")
        self.assertEqual(reconstructed.followup_task_id, task["id"])
        self.assertIn("followup_task_id", result.content)

    def test_evaluate_evolution_followup_decision_records_promotion_from_task_state(self) -> None:
        self._write_evolution_run("EVR-operator-decision")
        captured: dict[str, dict] = {}

        with patch(
            "sisyphus.evolution.bridge.request_task",
            side_effect=self._fake_request_task_factory(captured),
        ):
            followup = request_evolution_followup(
                self.repo_root,
                run_id="EVR-operator-decision",
                candidate_id="candidate-002",
                title="Decision candidate",
                summary="Create a review-gated follow-up task.",
                config=self.config,
            )

        task = captured["task"]
        self._configure_followup_results(task)

        decision = evaluate_evolution_followup_decision(
            self.repo_root,
            task_id=followup.task_id,
            config=self.config,
        )

        decision_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_DECISION_RECORDED
        ]

        self.assertEqual(decision.task_id, followup.task_id)
        self.assertEqual(decision.run_id, "EVR-operator-decision")
        self.assertEqual(decision.candidate_id, "candidate-002")
        self.assertEqual(decision.gate_status, EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE)
        self.assertEqual(decision.envelope_status, EVOLUTION_ENVELOPE_STATUS_PROMOTION)
        self.assertIn("evolution decision", decision.content)
        self.assertEqual(len(decision_events), 1)
        self.assertEqual(decision_events[0]["data"]["candidate_id"], "candidate-002")

    def test_evaluate_evolution_followup_decision_rejects_non_followup_task(self) -> None:
        task = self._new_task("plain-task")

        with self.assertRaisesRegex(ValueError, "evolution follow-up"):
            evaluate_evolution_followup_decision(
                self.repo_root,
                task_id=task["id"],
                config=self.config,
            )

    def test_evaluate_evolution_followup_decision_rejects_missing_run_artifacts(self) -> None:
        task = self._new_task("missing-run-artifacts")
        task.setdefault("meta", {})["source_context"] = {
            EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND: {
                "source_run_id": "EVR-missing",
                "candidate_id": "candidate-missing",
                "title": "Missing run",
                "summary": "This task points at a missing run.",
                "requested_task_type": "feature",
                "target_scope": ["execution-contract-wording"],
                "required_review_gates": list(EVOLUTION_DEFAULT_REVIEW_GATES),
                "request_only": True,
                "expected_verification_obligations": [
                    {
                        "claim": "preserves intent",
                        "method": "sisyphus verify",
                        "required": True,
                    }
                ],
                "evidence_summary": [
                    {
                        "kind": "report",
                        "summary": "missing run artifact",
                    }
                ],
            }
        }
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        with self.assertRaises(FileNotFoundError):
            evaluate_evolution_followup_decision(
                self.repo_root,
                task_id=task["id"],
                config=self.config,
            )


class EvolutionDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def test_dataset_includes_task_and_event_traces(self) -> None:
        task = self._new_task("dataset-default")
        append_conformance_log(
            task,
            checkpoint_type="post_exec",
            status="yellow",
            summary="needs verify follow-up",
            source="tests",
            resolved=False,
            drift=0,
        )
        task["verify_status"] = "passed"
        task["last_verified_at"] = "2026-04-13T12:00:00Z"
        task["last_verify_results"] = [
            {
                "command": "pytest tests/test_evolution.py",
                "status": "passed",
                "exit_code": 0,
                "started_at": "2026-04-13T11:59:58Z",
                "finished_at": "2026-04-13T12:00:00Z",
                "output_excerpt": "ok",
            }
        ]
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event_id": "evt_1",
                            "event_type": "conversation",
                            "timestamp": "2026-04-13T12:00:01Z",
                            "status": "processed",
                            "message": "created dataset task",
                            "result": {"task_id": task["id"]},
                        }
                    ),
                    json.dumps(
                        {
                            "event_id": "evt_2",
                            "event_type": "task.updated",
                            "timestamp": "2026-04-13T12:00:02Z",
                            "data": {"task_id": task["id"]},
                            "source": {"module": "workflow"},
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        dataset = build_evolution_dataset(self.repo_root)

        self.assertEqual(dataset.task_count, 1)
        self.assertEqual(dataset.event_count, 2)
        trace = dataset.task_traces[0]
        self.assertEqual(trace.task_id, task["id"])
        self.assertEqual(trace.verify_status, "passed")
        self.assertEqual(trace.conformance_status, "yellow")
        self.assertEqual(trace.unresolved_warning_count, 1)
        self.assertEqual(trace.conformance_history_count, 1)
        self.assertEqual(trace.verify_results[0].command, "pytest tests/test_evolution.py")
        self.assertEqual(dataset.event_traces[0].task_id, task["id"])
        self.assertEqual(dataset.event_traces[1].source_module, "workflow")

    def test_dataset_filtering_scopes_tasks_and_events(self) -> None:
        task_one = self._new_task("dataset-one")
        task_two = self._new_task("dataset-two")
        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    json.dumps({"event_id": "evt_1", "event_type": "task.updated", "data": {"task_id": task_one["id"]}}),
                    json.dumps({"event_id": "evt_2", "event_type": "task.updated", "data": {"task_id": task_two["id"]}}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        dataset = build_evolution_dataset(self.repo_root, task_ids=[task_two["id"], task_one["id"]])

        self.assertEqual(dataset.selected_task_ids, (task_one["id"], task_two["id"]))
        self.assertEqual([trace.task_id for trace in dataset.task_traces], [task_one["id"], task_two["id"]])
        self.assertEqual([trace.task_id for trace in dataset.event_traces], [task_one["id"], task_two["id"]])

    def test_dataset_rejects_unknown_task_ids(self) -> None:
        self._new_task("dataset-known")

        with self.assertRaisesRegex(ValueError, "unknown task ids: missing-task"):
            build_evolution_dataset(self.repo_root, task_ids=["missing-task"])

    def test_dataset_build_does_not_mutate_repo_files(self) -> None:
        task = self._new_task("dataset-immutable")
        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            json.dumps({"event_id": "evt_1", "event_type": "task.updated", "data": {"task_id": task["id"]}}) + "\n",
            encoding="utf-8",
        )

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        _ = build_evolution_dataset(self.repo_root, task_ids=[task["id"]])

        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        self.assertEqual(before, after)


class EvolutionHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _repo_files(self, root: Path | None = None) -> dict[str, str]:
        repo_root = root or self.repo_root
        return {
            path.relative_to(repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(repo_root.rglob("*"))
            if path.is_file()
        }

    def _seed_phase_1_sources(self, root: Path | None = None) -> None:
        repo_root = root or self.repo_root
        for source_path in ordered_target_source_paths(
            [
                "execution-contract-wording",
                "mcp-tool-descriptions",
                "agent-instruction-sections",
                "conformance-summary-wording",
                "review-gate-explanation-text",
            ]
        ):
            target_path = repo_root / source_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text((PROJECT_ROOT / source_path).read_text(encoding="utf-8"), encoding="utf-8")

    def _build_evaluation_task(self, task_id: str, worktree_root: Path) -> dict:
        task_dir = Path(".planning/tasks") / task_id
        (worktree_root / task_dir).mkdir(parents=True, exist_ok=True)
        return {
            "id": task_id,
            "task_dir": task_dir.as_posix(),
            "worktree_path": str(worktree_root),
            "branch": f"feat/{task_id.lower()}",
            "status": "open",
            "plan_status": "approved",
            "spec_status": "frozen",
            "workflow_phase": "subtask_planning",
        }

    def test_harness_plan_pairs_run_and_dataset(self) -> None:
        self._new_task("harness-plan")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording", "mcp-tool-descriptions"])
        dataset = build_evolution_dataset(self.repo_root)

        plan = plan_evolution_harness(run, dataset)

        self.assertEqual(plan.isolation_mode, EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY)
        self.assertFalse(plan.mutates_live_task_state)
        self.assertTrue(plan.requires_branch_snapshot)
        self.assertTrue(plan.requires_task_worktree_copy)
        self.assertTrue(plan.requires_result_capture)
        self.assertEqual(plan.baseline.status, EVOLUTION_EVALUATION_STATUS_PLANNED)
        self.assertEqual(plan.candidate.status, EVOLUTION_EVALUATION_STATUS_PLANNED)
        self.assertEqual(plan.baseline.target_ids, run.target_ids)
        self.assertEqual(plan.candidate.target_ids, run.target_ids)
        self.assertEqual(plan.dataset_task_ids, dataset.selected_task_ids)

    def test_harness_plan_keeps_metrics_containers_empty(self) -> None:
        self._new_task("harness-metrics")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)

        plan = plan_evolution_harness(run, dataset)

        self.assertIsNone(plan.baseline.metrics.verify_pass_rate)
        self.assertIsNone(plan.baseline.metrics.runtime_ms)
        self.assertIsNone(plan.candidate.metrics.operator_reviewability)
        self.assertIn("planned baseline evaluation", plan.baseline.notes)
        self.assertIn("isolated baseline and candidate execution", plan.notes)

    def test_harness_plan_candidate_narrowing_preserves_run_order(self) -> None:
        self._new_task("harness-scope")
        run = plan_evolution_run(
            self.repo_root,
            target_ids=[
                "execution-contract-wording",
                "mcp-tool-descriptions",
                "review-gate-explanation-text",
            ],
        )
        dataset = build_evolution_dataset(self.repo_root)

        plan = plan_evolution_harness(
            run,
            dataset,
            candidate_target_ids=[
                "review-gate-explanation-text",
                "execution-contract-wording",
            ],
        )

        self.assertEqual(
            plan.candidate.target_ids,
            ("execution-contract-wording", "review-gate-explanation-text"),
        )

    def test_harness_plan_rejects_invalid_scope_without_repo_mutation(self) -> None:
        self._new_task("harness-invalid")
        other_repo = Path(self.tempdir.name) / "other"
        other_repo.mkdir(parents=True, exist_ok=True)
        (other_repo / ".taskflow.toml").write_text("", encoding="utf-8")
        other_config = load_config(other_repo)
        other_task = create_task_record(
            repo_root=other_repo,
            config=other_config,
            task_type="feature",
            slug="other-task",
        )
        materialize_task_templates(other_task)

        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        other_dataset = build_evolution_dataset(other_repo)

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        with self.assertRaisesRegex(ValueError, "same repository root"):
            plan_evolution_harness(run, other_dataset)

        with self.assertRaisesRegex(ValueError, "outside the run scope: mcp-tool-descriptions"):
            plan_evolution_harness(run, dataset, candidate_target_ids=["mcp-tool-descriptions"])

        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        self.assertEqual(before, after)

    def test_materialize_baseline_captures_task_local_source_snapshots_without_source_rewrite(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("materialize-baseline")
        run = plan_evolution_run(
            self.repo_root,
            target_ids=["execution-contract-wording", "agent-instruction-sections"],
        )
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        evaluation_task = self._build_evaluation_task("TF-eval-baseline", self.repo_root)

        conformance_before = (self.repo_root / "src/sisyphus/conformance.py").read_text(encoding="utf-8")
        prompt_before = (self.repo_root / "src/sisyphus/codex_prompt.py").read_text(encoding="utf-8")

        materialization = materialize_evolution_evaluation(plan.baseline, task=evaluation_task)

        self.assertEqual(materialization.status, EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED)
        self.assertEqual(
            materialization.file_paths,
            ("src/sisyphus/conformance.py", "src/sisyphus/codex_prompt.py"),
        )
        self.assertEqual(
            (self.repo_root / "src/sisyphus/conformance.py").read_text(encoding="utf-8"),
            conformance_before,
        )
        self.assertEqual(
            (self.repo_root / "src/sisyphus/codex_prompt.py").read_text(encoding="utf-8"),
            prompt_before,
        )
        self.assertTrue((self.repo_root / materialization.manifest_path).is_file())
        self.assertTrue(
            (
                self.repo_root
                / materialization.snapshot_root
                / "src/sisyphus/conformance.py"
            ).is_file()
        )

    def test_materialize_candidate_applies_bounded_target_rewrites(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("materialize-candidate")
        run = plan_evolution_run(
            self.repo_root,
            target_ids=["execution-contract-wording", "review-gate-explanation-text"],
        )
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        evaluation_task = self._build_evaluation_task("TF-eval-candidate", self.repo_root)

        materialization = materialize_evolution_evaluation(plan.candidate, task=evaluation_task)
        conformance_text = (self.repo_root / "src/sisyphus/conformance.py").read_text(encoding="utf-8")
        audit_text = (self.repo_root / "src/sisyphus/audit.py").read_text(encoding="utf-8")

        self.assertEqual(materialization.status, EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED)
        self.assertEqual(
            tuple(target.target_id for target in materialization.targets),
            ("execution-contract-wording", "review-gate-explanation-text"),
        )
        self.assertIn("must be resolved before continuing", conformance_text)
        self.assertIn("before review can pass", audit_text)
        self.assertTrue((self.repo_root / materialization.manifest_path).is_file())
        self.assertTrue(
            (
                self.repo_root
                / materialization.snapshot_root
                / "src/sisyphus/audit.py"
            ).is_file()
        )

    def test_materialize_candidate_fails_loudly_when_anchor_is_missing(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("materialize-failure")
        conformance_path = self.repo_root / "src/sisyphus/conformance.py"
        conformance_path.write_text(
            conformance_path.read_text(encoding="utf-8").replace(
                "clarification or warning is pending",
                "unexpected candidate wording is already present",
            ),
            encoding="utf-8",
        )
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        evaluation_task = self._build_evaluation_task("TF-eval-failure", self.repo_root)

        with self.assertRaisesRegex(EvolutionMaterializationError, "bounded mutation anchor missing"):
            materialize_evolution_evaluation(plan.candidate, task=evaluation_task)

    def test_execute_sisyphus_evaluation_records_materialization_evidence_and_manifest_owned_path(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("harness-sisyphus-materialized")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        task_id = "TF-eval-materialized"
        evaluation_worktree = self.repo_root / "_worktrees" / task_id
        evaluation_worktree.mkdir(parents=True, exist_ok=True)
        self._seed_phase_1_sources(evaluation_worktree)
        task_snapshot = self._build_evaluation_task(task_id, evaluation_worktree)
        task_snapshots = {task_id: dict(task_snapshot)}
        wrapper_calls: dict[str, object] = {}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            task_snapshots[task_id] = dict(task_snapshot)
            return SimpleNamespace(ok=True, task_id=task_id, task=dict(task_snapshot), error=None)

        def fake_approve_task_plan(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["plan_status"] = "approved"
            return SimpleNamespace(plan_status="approved")

        def fake_freeze_task_spec(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["spec_status"] = "frozen"
            task_snapshots[task_id]["workflow_phase"] = "subtask_planning"
            return SimpleNamespace(spec_status="frozen", workflow_phase="subtask_planning")

        def fake_run_provider_wrapper(provider, argv, *, repo_root=None):
            wrapper_calls["provider"] = provider
            wrapper_calls["argv"] = argv
            wrapper_calls["repo_root"] = repo_root
            return 0

        def fake_load_task_record(repo_root, task_dir_name, task_id):
            return (
                dict(task_snapshots[task_id]),
                evaluation_worktree / ".planning" / "tasks" / task_id / "task.json",
            )

        request = build_sisyphus_evaluation_request(
            plan.candidate,
            dataset,
            auto_execute=True,
            owned_paths=["docs/self-evolution-mcp-plan.md"],
        )

        with (
            patch("sisyphus.api.request_task", side_effect=fake_request_task),
            patch("sisyphus.planning.approve_task_plan", side_effect=fake_approve_task_plan),
            patch("sisyphus.planning.freeze_task_spec", side_effect=fake_freeze_task_spec),
            patch("sisyphus.provider_wrapper.run_provider_wrapper", side_effect=fake_run_provider_wrapper),
            patch("sisyphus.state.load_task_record", side_effect=fake_load_task_record),
        ):
            outcome = execute_sisyphus_evaluation(plan.candidate, dataset, request=request)

        self.assertIsNotNone(outcome.evidence)
        self.assertEqual(outcome.evidence.mode, EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK)
        self.assertEqual(outcome.evidence.materialization_status, EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED)
        self.assertEqual(outcome.evidence.materialized_target_ids, plan.candidate.target_ids)
        self.assertEqual(outcome.evidence.materialized_file_paths, ("src/sisyphus/conformance.py",))
        self.assertTrue((evaluation_worktree / outcome.evidence.materialization_manifest_path).is_file())
        self.assertIn("--owned-path", wrapper_calls["argv"])
        self.assertIn("src/sisyphus/conformance.py", wrapper_calls["argv"])
        self.assertIn("docs/self-evolution-mcp-plan.md", wrapper_calls["argv"])
        self.assertIn(outcome.evidence.materialization_manifest_path, wrapper_calls["argv"])
        self.assertIn(
            "must be resolved before continuing",
            (evaluation_worktree / "src/sisyphus/conformance.py").read_text(encoding="utf-8"),
        )

    def test_build_worktree_evaluation_command_plan_normalizes_and_dedupes_commands(self) -> None:
        task = self._new_task("worktree-command-plan")
        task["last_verify_results"] = [
            {
                "command": f"cd {self.repo_root / '_worktrees' / 'old-task'} && {sys.executable} -c \"print('alpha')\"",
                "status": "passed",
                "exit_code": 0,
            },
            {
                "command": f"cd {self.repo_root / '_worktrees' / 'old-task'} && {sys.executable} -c \"print('alpha')\"",
                "status": "passed",
                "exit_code": 0,
            },
        ]
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)

        commands = build_worktree_evaluation_command_plan(plan.baseline, dataset)

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].source_task_id, task["id"])
        self.assertEqual(commands[0].source, "verify_result")
        self.assertNotIn("cd ", commands[0].normalized_command)
        self.assertIn("print('alpha')", commands[0].normalized_command)

    def test_execute_worktree_backed_evaluation_persists_receipt_and_runtime_metrics(self) -> None:
        self._seed_phase_1_sources()
        task = self._new_task("worktree-executor")
        task["verify_commands"] = [
            f"cd {self.repo_root / '_worktrees' / 'stale'} && {sys.executable} -c \"from pathlib import Path; assert Path('src/sisyphus/conformance.py').is_file(); print('ok')\""
        ]
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        task_id = "TF-eval-worktree-success"
        evaluation_worktree = self.repo_root / "_worktrees" / task_id
        evaluation_worktree.mkdir(parents=True, exist_ok=True)
        self._seed_phase_1_sources(evaluation_worktree)
        task_snapshot = self._build_evaluation_task(task_id, evaluation_worktree)
        task_snapshots = {task_id: dict(task_snapshot)}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            task_snapshots[task_id] = dict(task_snapshot)
            return SimpleNamespace(ok=True, task_id=task_id, task=dict(task_snapshot), error=None)

        def fake_approve_task_plan(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["plan_status"] = "approved"
            return SimpleNamespace(plan_status="approved")

        def fake_freeze_task_spec(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["spec_status"] = "frozen"
            task_snapshots[task_id]["workflow_phase"] = "subtask_planning"
            return SimpleNamespace(spec_status="frozen", workflow_phase="subtask_planning")

        def fake_load_task_record(repo_root, task_dir_name, task_id):
            return (
                dict(task_snapshots[task_id]),
                evaluation_worktree / ".planning" / "tasks" / task_id / "task.json",
            )

        with (
            patch("sisyphus.api.request_task", side_effect=fake_request_task),
            patch("sisyphus.planning.approve_task_plan", side_effect=fake_approve_task_plan),
            patch("sisyphus.planning.freeze_task_spec", side_effect=fake_freeze_task_spec),
            patch("sisyphus.state.load_task_record", side_effect=fake_load_task_record),
        ):
            outcome = execute_worktree_backed_evaluation(plan.candidate, dataset)

        self.assertEqual(outcome.evidence.mode, EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS)
        self.assertEqual(outcome.evidence.command_count, 1)
        self.assertEqual(outcome.evidence.passed_command_count, 1)
        self.assertEqual(outcome.metrics.verify_pass_rate, 1.0)
        self.assertGreater(outcome.metrics.runtime_ms or 0, 0)
        self.assertTrue((evaluation_worktree / (outcome.evidence.execution_receipt_path or "")).is_file())

    def test_execute_worktree_backed_evaluation_fails_with_receipt_on_command_error(self) -> None:
        self._seed_phase_1_sources()
        task = self._new_task("worktree-executor-failure")
        task["verify_commands"] = [
            f"{sys.executable} -c \"import sys; print('boom'); sys.exit(3)\""
        ]
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        task_id = "TF-eval-worktree-failure"
        evaluation_worktree = self.repo_root / "_worktrees" / task_id
        evaluation_worktree.mkdir(parents=True, exist_ok=True)
        self._seed_phase_1_sources(evaluation_worktree)
        task_snapshot = self._build_evaluation_task(task_id, evaluation_worktree)
        task_snapshots = {task_id: dict(task_snapshot)}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            task_snapshots[task_id] = dict(task_snapshot)
            return SimpleNamespace(ok=True, task_id=task_id, task=dict(task_snapshot), error=None)

        def fake_approve_task_plan(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["plan_status"] = "approved"
            return SimpleNamespace(plan_status="approved")

        def fake_freeze_task_spec(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["spec_status"] = "frozen"
            task_snapshots[task_id]["workflow_phase"] = "subtask_planning"
            return SimpleNamespace(spec_status="frozen", workflow_phase="subtask_planning")

        def fake_load_task_record(repo_root, task_dir_name, task_id):
            return (
                dict(task_snapshots[task_id]),
                evaluation_worktree / ".planning" / "tasks" / task_id / "task.json",
            )

        with (
            patch("sisyphus.api.request_task", side_effect=fake_request_task),
            patch("sisyphus.planning.approve_task_plan", side_effect=fake_approve_task_plan),
            patch("sisyphus.planning.freeze_task_spec", side_effect=fake_freeze_task_spec),
            patch("sisyphus.state.load_task_record", side_effect=fake_load_task_record),
        ):
            with self.assertRaises(EvolutionEvaluationExecutionError) as excinfo:
                execute_worktree_backed_evaluation(plan.candidate, dataset)

        error = excinfo.exception
        self.assertEqual(error.evidence.mode, EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS)
        self.assertEqual(error.evidence.command_count, 1)
        self.assertEqual(error.evidence.passed_command_count, 0)
        self.assertEqual(error.metrics.verify_pass_rate, 0.0)
        self.assertTrue((evaluation_worktree / (error.evidence.execution_receipt_path or "")).is_file())

    def test_execute_harness_populates_default_metrics_without_repo_mutation(self) -> None:
        task_one = self._new_task("harness-exec-one")
        task_one["verify_status"] = "passed"
        save_task_record(self.repo_root / task_one["task_dir"] / "task.json", task_one)

        task_two = self._new_task("harness-exec-two")
        append_conformance_log(
            task_two,
            checkpoint_type="post_exec",
            status="yellow",
            summary="needs follow-up",
            source="tests",
            resolved=False,
            drift=0,
        )
        task_two["verify_status"] = "failed"
        save_task_record(self.repo_root / task_two["task_dir"] / "task.json", task_two)

        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }
        executed = execute_evolution_harness(plan, dataset)
        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        self.assertEqual(before, after)
        self.assertEqual(executed.baseline.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.candidate.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.baseline.metrics.verify_pass_rate, 0.5)
        self.assertEqual(executed.baseline.metrics.conformance_status, "yellow")
        self.assertEqual(executed.baseline.metrics.drift_count, 0)
        self.assertEqual(executed.baseline.metrics.unresolved_warning_count, 1)
        self.assertGreater(executed.baseline.metrics.runtime_ms or 0, 0)
        self.assertEqual(executed.baseline.metrics.operator_reviewability, "low")
        self.assertIn("executed baseline and candidate", executed.notes)

    def test_execute_harness_supports_custom_executor_and_scores_results(self) -> None:
        self._new_task("harness-custom")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording", "mcp-tool-descriptions"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

        def executor(evaluation, selected_dataset):
            calls.append((evaluation.role, evaluation.task_ids, selected_dataset.selected_task_ids))
            if evaluation.role == "baseline":
                return EvolutionPlannedMetrics(
                    verify_pass_rate=0.8,
                    conformance_status="yellow",
                    drift_count=1,
                    unresolved_warning_count=1,
                    token_estimate=1200,
                    operator_reviewability="medium",
                )
            return EvolutionPlannedMetrics(
                verify_pass_rate=1.0,
                conformance_status="green",
                drift_count=0,
                unresolved_warning_count=1,
                token_estimate=900,
                operator_reviewability="high",
            )

        executed = execute_evolution_harness(plan, dataset, executor=executor)
        constraints = evaluate_evolution_constraints(
            executed,
            warning_increase_threshold=0,
            mcp_compatibility_ok=True,
            output_contract_stable=True,
        )
        fitness = evaluate_evolution_fitness(executed, constraints=constraints)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], dataset.selected_task_ids)
        self.assertEqual(calls[0][2], dataset.selected_task_ids)
        self.assertEqual(calls[1][1], dataset.selected_task_ids)
        self.assertEqual(calls[1][2], dataset.selected_task_ids)
        self.assertEqual(executed.baseline.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.candidate.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(constraints.status, "accepted")
        self.assertEqual(fitness.status, "scored")
        self.assertTrue(fitness.eligible_for_promotion)

    def test_execute_harness_supports_sisyphus_evaluation_evidence(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("harness-sisyphus")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        task_snapshots: dict[str, dict[str, object]] = {}
        wrapper_calls: list[tuple[str, list[str]]] = []

        def fake_request_task(repo_root, *, config=None, **kwargs):
            task_id = f"TF-eval-{kwargs['slug']}"
            worktree_root = self.repo_root / "_worktrees" / task_id
            worktree_root.mkdir(parents=True, exist_ok=True)
            self._seed_phase_1_sources(worktree_root)
            task = self._build_evaluation_task(task_id, worktree_root)
            task["plan_status"] = "pending_review"
            task["spec_status"] = "draft"
            task["workflow_phase"] = "plan_in_review"
            task_snapshots[task_id] = dict(task)
            return SimpleNamespace(ok=True, task_id=task_id, task=task, error=None)

        def fake_approve_task_plan(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["plan_status"] = "approved"
            return SimpleNamespace(plan_status="approved")

        def fake_freeze_task_spec(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["spec_status"] = "frozen"
            task_snapshots[task_id]["workflow_phase"] = "subtask_planning"
            return SimpleNamespace(spec_status="frozen", workflow_phase="subtask_planning")

        def fake_run_provider_wrapper(provider, argv, *, repo_root=None):
            wrapper_calls.append((provider, argv))
            task_snapshots[argv[1]]["status"] = "open"
            return 0

        def fake_load_task_record(repo_root, task_dir_name, task_id):
            return (
                dict(task_snapshots[task_id]),
                self.repo_root / ".planning" / "tasks" / task_id / "task.json",
            )

        def executor(evaluation, selected_dataset):
            request = build_sisyphus_evaluation_request(
                evaluation,
                selected_dataset,
                auto_execute=evaluation.role == "candidate",
                owned_paths=["docs/self-evolution-mcp-plan.md"],
            )
            return execute_sisyphus_evaluation(evaluation, selected_dataset, request=request)

        with (
            patch("sisyphus.api.request_task", side_effect=fake_request_task),
            patch("sisyphus.planning.approve_task_plan", side_effect=fake_approve_task_plan),
            patch("sisyphus.planning.freeze_task_spec", side_effect=fake_freeze_task_spec),
            patch("sisyphus.provider_wrapper.run_provider_wrapper", side_effect=fake_run_provider_wrapper),
            patch("sisyphus.state.load_task_record", side_effect=fake_load_task_record),
        ):
            executed = execute_evolution_harness(plan, dataset, executor=executor)

        self.assertEqual(executed.baseline.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.candidate.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.baseline.evidence.mode, EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK)
        self.assertIn("TF-eval-", executed.baseline.evidence.task_id or "")
        self.assertIsNone(executed.baseline.evidence.exit_code)
        self.assertEqual(executed.candidate.evidence.exit_code, 0)
        self.assertEqual(executed.candidate.evidence.spec_status, "frozen")
        self.assertEqual(len(wrapper_calls), 1)
        self.assertEqual(wrapper_calls[0][0], "codex")
        self.assertEqual(wrapper_calls[0][1][0], "task")

    def test_execute_harness_captures_sisyphus_evaluation_failure(self) -> None:
        self._seed_phase_1_sources()
        self._new_task("harness-sisyphus-failure")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        task_snapshots: dict[str, dict[str, object]] = {}

        def fake_request_task(repo_root, *, config=None, **kwargs):
            task_id = f"TF-eval-{kwargs['slug']}"
            worktree_root = self.repo_root / "_worktrees" / task_id
            worktree_root.mkdir(parents=True, exist_ok=True)
            self._seed_phase_1_sources(worktree_root)
            task = self._build_evaluation_task(task_id, worktree_root)
            task["plan_status"] = "pending_review"
            task["spec_status"] = "draft"
            task["workflow_phase"] = "plan_in_review"
            task_snapshots[task_id] = dict(task)
            return SimpleNamespace(ok=True, task_id=task_id, task=task, error=None)

        def fake_approve_task_plan(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["plan_status"] = "approved"
            return SimpleNamespace(plan_status="approved")

        def fake_freeze_task_spec(repo_root, config, task_id, *, reviewer, notes):
            task_snapshots[task_id]["spec_status"] = "frozen"
            task_snapshots[task_id]["workflow_phase"] = "subtask_planning"
            return SimpleNamespace(spec_status="frozen", workflow_phase="subtask_planning")

        def fake_run_provider_wrapper(provider, argv, *, repo_root=None):
            if "candidate" in argv[1]:
                task_snapshots[argv[1]]["status"] = "blocked"
                return 9
            return 0

        def fake_load_task_record(repo_root, task_dir_name, task_id):
            return (
                dict(task_snapshots[task_id]),
                self.repo_root / ".planning" / "tasks" / task_id / "task.json",
            )

        def executor(evaluation, selected_dataset):
            request = build_sisyphus_evaluation_request(
                evaluation,
                selected_dataset,
                auto_execute=True,
            )
            return execute_sisyphus_evaluation(evaluation, selected_dataset, request=request)

        with (
            patch("sisyphus.api.request_task", side_effect=fake_request_task),
            patch("sisyphus.planning.approve_task_plan", side_effect=fake_approve_task_plan),
            patch("sisyphus.planning.freeze_task_spec", side_effect=fake_freeze_task_spec),
            patch("sisyphus.provider_wrapper.run_provider_wrapper", side_effect=fake_run_provider_wrapper),
            patch("sisyphus.state.load_task_record", side_effect=fake_load_task_record),
        ):
            executed = execute_evolution_harness(plan, dataset, executor=executor)

        self.assertEqual(executed.baseline.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.candidate.status, EVOLUTION_EVALUATION_STATUS_FAILED)
        self.assertEqual(executed.candidate.evidence.mode, EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK)
        self.assertEqual(executed.candidate.evidence.exit_code, 9)
        self.assertEqual(executed.candidate.metrics.verify_pass_rate, 0.0)
        self.assertIn("exited with code 9", executed.candidate.notes)

    def test_execute_harness_captures_failed_evaluation_without_repo_mutation(self) -> None:
        self._new_task("harness-failure")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)

        def executor(evaluation, selected_dataset):
            if evaluation.role == "candidate":
                raise RuntimeError("candidate crashed")
            return EvolutionPlannedMetrics(
                verify_pass_rate=1.0,
                conformance_status="green",
                drift_count=0,
                unresolved_warning_count=0,
                operator_reviewability="high",
            )

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }
        executed = execute_evolution_harness(plan, dataset, executor=executor)
        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        self.assertEqual(before, after)
        self.assertEqual(executed.baseline.status, EVOLUTION_EVALUATION_STATUS_COMPLETED)
        self.assertEqual(executed.candidate.status, EVOLUTION_EVALUATION_STATUS_FAILED)
        self.assertGreater(executed.candidate.metrics.runtime_ms or 0, 0)
        self.assertEqual(
            executed.candidate.metrics.operator_reviewability,
            EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED,
        )
        self.assertIn("candidate evaluation failed: candidate crashed", executed.candidate.notes)


class EvolutionConstraintsAndFitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _build_plan(self):
        self._new_task("scoring-target")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording", "mcp-tool-descriptions"])
        dataset = build_evolution_dataset(self.repo_root)
        plan = plan_evolution_harness(run, dataset)
        return run, dataset, plan

    def _plan_with_metrics(
        self,
        *,
        baseline: EvolutionPlannedMetrics,
        candidate: EvolutionPlannedMetrics,
    ):
        run, dataset, plan = self._build_plan()
        plan = replace(
            plan,
            baseline=replace(plan.baseline, metrics=baseline),
            candidate=replace(plan.candidate, metrics=candidate),
        )
        return run, dataset, plan

    def test_constraints_stay_pending_without_comparable_metrics(self) -> None:
        _, _, plan = self._build_plan()

        result = evaluate_evolution_constraints(plan)

        self.assertEqual(result.status, "pending")
        self.assertIsNone(result.accepted)
        self.assertEqual(result.blocking_failure_count, 0)
        self.assertEqual(result.pending_guard_count, 5)
        self.assertTrue(all(check.status == "pending" for check in result.checks))

    def test_constraints_respect_warning_threshold_and_fitness_scores_candidate(self) -> None:
        _, _, plan = self._plan_with_metrics(
            baseline=EvolutionPlannedMetrics(
                verify_pass_rate=0.95,
                conformance_status="yellow",
                drift_count=1,
                unresolved_warning_count=1,
                runtime_ms=1600,
                token_estimate=1400,
                operator_reviewability="medium",
            ),
            candidate=EvolutionPlannedMetrics(
                verify_pass_rate=0.95,
                conformance_status="green",
                drift_count=1,
                unresolved_warning_count=2,
                runtime_ms=900,
                token_estimate=900,
                operator_reviewability="high",
            ),
        )

        constraints = evaluate_evolution_constraints(
            plan,
            warning_increase_threshold=1,
            mcp_compatibility_ok=True,
            output_contract_stable=True,
        )
        fitness = evaluate_evolution_fitness(plan, constraints=constraints)

        self.assertEqual(constraints.status, "accepted")
        self.assertTrue(constraints.accepted)
        self.assertEqual(fitness.status, "scored")
        self.assertTrue(fitness.eligible_for_promotion)
        self.assertGreater(fitness.candidate_score or 0.0, fitness.baseline_score or 0.0)
        self.assertGreater(fitness.score_delta or 0.0, 0.0)

    def test_constraints_reject_regressions_without_repo_mutation(self) -> None:
        _, dataset, plan = self._plan_with_metrics(
            baseline=EvolutionPlannedMetrics(
                verify_pass_rate=1.0,
                conformance_status="green",
                drift_count=0,
                unresolved_warning_count=0,
                runtime_ms=800,
                operator_reviewability="high",
            ),
            candidate=EvolutionPlannedMetrics(
                verify_pass_rate=0.75,
                conformance_status="red",
                drift_count=2,
                unresolved_warning_count=3,
                runtime_ms=1500,
                operator_reviewability="low",
            ),
        )

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        constraints = evaluate_evolution_constraints(
            plan,
            mcp_compatibility_ok=False,
            output_contract_stable=False,
        )
        fitness = evaluate_evolution_fitness(plan, constraints=constraints)

        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        failed_guards = {check.guard_id for check in constraints.checks if check.status == "failed"}
        self.assertEqual(dataset.selected_task_ids, plan.dataset_task_ids)
        self.assertEqual(constraints.status, "rejected")
        self.assertFalse(constraints.accepted)
        self.assertEqual(
            failed_guards,
            {
                "verify-pass-rate",
                "conformance-drift",
                "unresolved-warnings",
                "mcp-compatibility",
                "output-contract-stability",
            },
        )
        self.assertEqual(fitness.status, "rejected")
        self.assertFalse(fitness.eligible_for_promotion)
        self.assertEqual(before, after)


class EvolutionReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _build_report_inputs(self, *, with_metrics: bool = False):
        self._new_task("report-target")
        run = plan_evolution_run(self.repo_root, target_ids=["execution-contract-wording"])
        dataset = build_evolution_dataset(self.repo_root)
        harness = plan_evolution_harness(run, dataset)
        if not with_metrics:
            return run, dataset, harness, None, None

        harness = replace(
            harness,
            baseline=replace(
                harness.baseline,
                metrics=EvolutionPlannedMetrics(
                    verify_pass_rate=0.9,
                    conformance_status="yellow",
                    drift_count=1,
                    unresolved_warning_count=1,
                    runtime_ms=1200,
                    operator_reviewability="medium",
                ),
            ),
            candidate=replace(
                harness.candidate,
                metrics=EvolutionPlannedMetrics(
                    verify_pass_rate=0.95,
                    conformance_status="green",
                    drift_count=0,
                    unresolved_warning_count=1,
                    runtime_ms=900,
                    operator_reviewability="high",
                ),
            ),
        )
        constraints = evaluate_evolution_constraints(
            harness,
            mcp_compatibility_ok=True,
            output_contract_stable=True,
        )
        fitness = evaluate_evolution_fitness(harness, constraints=constraints)
        return run, dataset, harness, constraints, fitness

    def test_report_models_planned_run_with_placeholders(self) -> None:
        run, dataset, harness, constraints, fitness = self._build_report_inputs()

        report = build_evolution_report(
            run,
            dataset,
            harness,
            constraint_result=constraints,
            fitness_result=fitness,
        )

        self.assertEqual(report.status, "planned")
        self.assertEqual(report.recommendation, "await_execution")
        self.assertIn("awaiting executed comparison data", report.headline)
        self.assertEqual(report.scope.target_ids, run.target_ids)
        self.assertEqual(report.dataset.task_count, 1)
        self.assertEqual(report.comparison_placeholders[0].status, "pending")
        self.assertEqual(report.comparison_placeholders[1].status, "pending")

    def test_report_surfaces_scored_candidate_for_review(self) -> None:
        run, dataset, harness, constraints, fitness = self._build_report_inputs(with_metrics=True)

        report = build_evolution_report(
            run,
            dataset,
            harness,
            constraint_result=constraints,
            fitness_result=fitness,
        )

        self.assertEqual(report.status, "ready_for_review")
        self.assertEqual(report.recommendation, "review_candidate")
        self.assertEqual(report.constraint_result.status, "accepted")
        self.assertEqual(report.fitness_result.status, "scored")
        self.assertEqual(report.comparison_placeholders[0].status, "available")
        self.assertEqual(report.comparison_placeholders[1].status, "available")
        self.assertIn("candidate", report.summary_lines[3])

    def test_report_rejects_mismatched_inputs_without_repo_mutation(self) -> None:
        run, dataset, harness, _, _ = self._build_report_inputs()
        other_repo = Path(self.tempdir.name) / "other"
        other_repo.mkdir(parents=True, exist_ok=True)
        (other_repo / ".taskflow.toml").write_text("", encoding="utf-8")
        other_config = load_config(other_repo)
        other_task = create_task_record(
            repo_root=other_repo,
            config=other_config,
            task_type="feature",
            slug="other-task",
        )
        materialize_task_templates(other_task)
        other_dataset = build_evolution_dataset(other_repo)

        before = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        with self.assertRaisesRegex(ValueError, "same repository root"):
            build_evolution_report(run, other_dataset, harness)

        after = {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
        }

        self.assertEqual(dataset.selected_task_ids, harness.dataset_task_ids)
        self.assertEqual(before, after)


class EvolutionOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _repo_snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file()
            and ".planning/evolution/runs/" not in path.as_posix()
            and path.relative_to(self.repo_root).as_posix() != ".planning/events.jsonl"
        }

    def test_execute_run_persists_expected_stage_artifacts(self) -> None:
        task = self._new_task("orchestrator-run")
        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            json.dumps({"event_id": "evt-1", "event_type": "task.updated", "data": {"task_id": task["id"]}}) + "\n",
            encoding="utf-8",
        )
        before = self._repo_snapshot()

        executed = execute_evolution_run(self.repo_root, run_id="EVR-orchestrator-success")

        after = self._repo_snapshot()
        artifact_dir = self.repo_root / ".planning" / "evolution" / "runs" / "EVR-orchestrator-success"
        self.assertEqual(executed.final_stage, EVOLUTION_STAGE_REPORT_BUILT)
        self.assertIsNone(executed.failure)
        self.assertEqual(before, after)
        self.assertTrue((artifact_dir / "run.json").exists())
        self.assertTrue((artifact_dir / "dataset.json").exists())
        self.assertTrue((artifact_dir / "harness_plan.json").exists())
        self.assertTrue((artifact_dir / "constraints.json").exists())
        self.assertTrue((artifact_dir / "fitness.json").exists())
        self.assertTrue((artifact_dir / "report.md").exists())

        constraints_payload = json.loads((artifact_dir / "constraints.json").read_text(encoding="utf-8"))
        fitness_payload = json.loads((artifact_dir / "fitness.json").read_text(encoding="utf-8"))
        self.assertEqual(constraints_payload["status"], "pending")
        self.assertEqual(fitness_payload["status"], "pending")
        evolution_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_RUN_RECORDED
        ]
        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-orchestrator-success")
        self.assertEqual(evolution_events[0]["data"]["final_stage"], EVOLUTION_STAGE_REPORT_BUILT)

    def test_execute_run_persists_pending_results_without_fabricating_metrics(self) -> None:
        self._new_task("orchestrator-pending")

        executed = execute_evolution_run(self.repo_root, run_id="EVR-orchestrator-pending")

        self.assertEqual(executed.constraint_result.status, "pending")
        self.assertIsNone(executed.constraint_result.accepted)
        self.assertEqual(executed.fitness_result.status, "pending")
        self.assertIsNone(executed.fitness_result.score_delta)
        self.assertEqual(executed.report.status, "planned")

    def test_execute_run_persists_stage_failure_without_live_repo_mutation(self) -> None:
        self._new_task("orchestrator-failure")
        before = self._repo_snapshot()

        def _broken_report_builder(*args, **kwargs):
            raise RuntimeError("report build exploded")

        with self.assertRaises(EvolutionRunExecutionError) as ctx:
            execute_evolution_run(
                self.repo_root,
                run_id="EVR-orchestrator-failure",
                report_builder=_broken_report_builder,
            )

        after = self._repo_snapshot()
        artifact_dir = self.repo_root / ".planning" / "evolution" / "runs" / "EVR-orchestrator-failure"
        failure_payload = json.loads((artifact_dir / "failure.json").read_text(encoding="utf-8"))

        self.assertEqual(before, after)
        self.assertEqual(ctx.exception.result.final_stage, EVOLUTION_STAGE_FAILED)
        self.assertEqual(ctx.exception.result.failure.stage, "report_built")
        self.assertEqual(failure_payload["stage"], "report_built")
        self.assertIn("fitness.json", failure_payload["partial_artifacts"])
        self.assertEqual(failure_payload["error_type"], "RuntimeError")
        evolution_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_RUN_FAILED
        ]
        self.assertEqual(len(evolution_events), 1)
        self.assertEqual(evolution_events[0]["data"]["run_id"], "EVR-orchestrator-failure")
        self.assertEqual(evolution_events[0]["data"]["failure_stage"], "report_built")


class EvolutionArtifactCycleEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _seed_phase_1_sources(
        self,
        root: Path,
        target_ids: tuple[str, ...] = ("execution-contract-wording",),
    ) -> None:
        for source_path in ordered_target_source_paths(target_ids):
            target_path = root / source_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                (PROJECT_ROOT / source_path).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def _build_evaluation_task(self, task_id: str, worktree_root: Path) -> dict:
        task_dir = Path(".planning/tasks") / task_id
        (worktree_root / task_dir).mkdir(parents=True, exist_ok=True)
        return {
            "id": task_id,
            "task_dir": task_dir.as_posix(),
            "worktree_path": str(worktree_root),
            "branch": f"feat/{task_id.lower()}",
            "status": "open",
            "plan_status": "approved",
            "spec_status": "frozen",
            "workflow_phase": "subtask_planning",
        }

    def _fake_request_task_factory(self, captured: dict[str, dict]) -> object:
        def fake_request_task(repo_root, *, config=None, **kwargs):
            task = create_task_record(
                repo_root=repo_root,
                config=config or self.config,
                task_type=kwargs["task_type"],
                slug=kwargs["slug"],
            )
            materialize_task_templates(task)
            task.setdefault("meta", {})["source_context"] = kwargs["source_context"]
            save_task_record(self.repo_root / task["task_dir"] / "task.json", task)
            captured["task"] = task
            return SimpleNamespace(ok=True, task_id=task["id"], task=task, error=None)

        return fake_request_task

    def _configure_followup_results(
        self,
        task: dict,
        *,
        verify_status: str = "passed",
        include_promotion_receipt: bool = True,
    ) -> None:
        task_dir = self.repo_root / task["task_dir"]
        task["verify_status"] = verify_status
        task["last_verify_results"] = [
            {
                "command": "python -m unittest -q tests.test_evolution",
                "status": verify_status,
                "exit_code": 0 if verify_status == "passed" else 1,
                "started_at": "2026-04-20T00:00:00Z",
                "finished_at": "2026-04-20T00:00:01Z",
                "output_excerpt": "ok" if verify_status == "passed" else "boom",
            }
        ]
        if include_promotion_receipt:
            promotion_relative = task["docs"]["promotion"]
            promotion_path = task_dir / promotion_relative
            promotion_path.parent.mkdir(parents=True, exist_ok=True)
            promotion_path.write_text("{\"recorded\": true}\n", encoding="utf-8")
            task.setdefault("meta", {})["promotion"] = {"receipt_path": promotion_relative}
        save_task_record(task_dir / "task.json", task)

    def _evolution_event_types(self) -> tuple[str, ...]:
        return tuple(
            str(event.get("event_type"))
            for event in _load_repo_events(self.repo_root)
            if str(event.get("event_type", "")).startswith("evolution.")
        )

    def test_happy_path_artifact_cycle_keeps_lineage_aligned(self) -> None:
        self._new_task("e2e-artifact-cycle")

        executed_run = execute_evolution_run(
            self.repo_root,
            run_id="EVR-e2e-happy",
            config=self.config,
            target_ids=["execution-contract-wording"],
        )
        plan = plan_evolution_harness(executed_run.run, executed_run.dataset)
        evaluation_worktree = self.repo_root / "_worktrees" / "TF-e2e-eval"
        evaluation_worktree.mkdir(parents=True, exist_ok=True)
        self._seed_phase_1_sources(evaluation_worktree)
        materialization = materialize_evolution_evaluation(
            plan.candidate,
            task=self._build_evaluation_task("TF-e2e-eval", evaluation_worktree),
        )
        candidate_id = "candidate-e2e-happy"

        followup_request = EvolutionFollowupRequest(
            source_run_id=executed_run.run.run_id,
            candidate_id=candidate_id,
            title="Follow up accepted evolution candidate",
            summary="Create a normal Sisyphus follow-up task for the accepted candidate.",
            requested_task_type="feature",
            target_scope=plan.candidate.target_ids,
            instruction_set=("Preserve existing review gates.",),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="follow-up execution remains reviewable",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="report",
                    summary="run report recommends promotion",
                    locator=f".planning/evolution/runs/{executed_run.run.run_id}/report.md",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )
        captured: dict[str, dict] = {}

        with patch(
            "sisyphus.evolution.bridge.request_task",
            side_effect=self._fake_request_task_factory(captured),
        ):
            bridged = bridge_evolution_followup_request(
                self.repo_root,
                followup_request,
                config=self.config,
                slug="e2e-artifact-followup",
            )

        followup_task = captured["task"]
        self._configure_followup_results(followup_task)

        execution_projection = project_followup_execution(
            self.repo_root,
            self.config,
            bridged.task_id,
        )
        verification_projection = project_followup_verification(
            self.repo_root,
            self.config,
            bridged.task_id,
        )
        gate = evaluate_evolution_promotion_gate(
            bridged.artifact,
            constraints=SimpleNamespace(
                accepted=True,
                status="accepted",
                notes="hard guards passed",
            ),
            fitness=SimpleNamespace(
                eligible_for_promotion=True,
                status="scored",
                notes="fitness supports promotion",
            ),
            execution_projection=execution_projection,
            verification_projection=verification_projection,
        )
        decision = record_evolution_decision_envelope(
            gate,
            claim="candidate remains promotion eligible",
            repo_root=self.repo_root,
            config=self.config,
        )
        invalidation = evaluate_evolution_invalidation(
            bridged.artifact,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_EXECUTION_RECEIPT,
                    detail="follow-up verify receipt changed after rerun",
                    stale_artifact_refs=tuple(
                        receipt.to_ref(notes=receipt.receipt_kind)
                        for receipt in execution_projection.execution_receipts
                    ),
                ),
            ),
        )

        self.assertEqual(materialization.status, EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED)
        self.assertEqual(bridged.artifact.run_id, executed_run.run.run_id)
        self.assertEqual(execution_projection.source_run_id, executed_run.run.run_id)
        self.assertEqual(verification_projection.source_run_id, executed_run.run.run_id)
        self.assertEqual(gate.status, EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE)
        self.assertEqual(decision.status, EVOLUTION_ENVELOPE_STATUS_PROMOTION)
        self.assertEqual(decision.promotion_decision.followup_task_id, bridged.task_id)
        self.assertEqual(invalidation.run_id, executed_run.run.run_id)
        self.assertEqual(invalidation.candidate_id, candidate_id)
        self.assertEqual(
            invalidation.remediation_actions,
            (
                EVOLUTION_INVALIDATION_ACTION_REPROJECT_RECEIPTS,
                EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
                EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
                EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
            ),
        )
        self.assertTrue(
            {
                EVOLUTION_EVENT_RUN_RECORDED,
                EVOLUTION_EVENT_FOLLOWUP_REQUESTED,
                EVOLUTION_EVENT_EXECUTION_PROJECTED,
                EVOLUTION_EVENT_VERIFICATION_PROJECTED,
                EVOLUTION_EVENT_DECISION_RECORDED,
            }.issubset(set(self._evolution_event_types()))
        )

    def test_blocked_artifact_cycle_records_invalidation_path(self) -> None:
        self._new_task("e2e-artifact-cycle-blocked")
        executed_run = execute_evolution_run(
            self.repo_root,
            run_id="EVR-e2e-blocked",
            config=self.config,
        )
        followup_request = EvolutionFollowupRequest(
            source_run_id=executed_run.run.run_id,
            candidate_id="candidate-blocked",
            title="Blocked follow-up candidate",
            summary="Create a follow-up request that will stay blocked.",
            requested_task_type="feature",
            target_scope=("execution-contract-wording",),
            instruction_set=(),
            owned_paths=("docs/architecture.md",),
            expected_verification_obligations=(
                EvolutionVerificationObligation(
                    claim="blocked path still preserves lineage",
                    method="tests.test_evolution",
                ),
            ),
            evidence_summary=(
                EvolutionEvidenceSummary(
                    kind="report",
                    summary="blocked candidate still needs a reviewable record",
                ),
            ),
            promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        )
        captured: dict[str, dict] = {}

        with patch(
            "sisyphus.evolution.bridge.request_task",
            side_effect=self._fake_request_task_factory(captured),
        ):
            bridged = bridge_evolution_followup_request(
                self.repo_root,
                followup_request,
                config=self.config,
                slug="e2e-artifact-blocked-followup",
            )

        gate = evaluate_evolution_promotion_gate(
            bridged.artifact,
            constraints=SimpleNamespace(
                accepted=False,
                status="rejected",
                notes="hard guards failed",
            ),
            fitness=SimpleNamespace(
                eligible_for_promotion=False,
                status="rejected",
                notes="fitness rejected",
            ),
        )
        decision = record_evolution_decision_envelope(
            gate,
            claim="candidate remains blocked",
            repo_root=self.repo_root,
            config=self.config,
        )
        invalidation = evaluate_evolution_invalidation(
            bridged.artifact,
            changes=(
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES,
                    detail="review gate policy changed after the blocked decision",
                ),
                EvolutionInvalidationChange(
                    change_kind=EVOLUTION_INVALIDATION_CHANGE_ENVELOPE,
                    detail="blocked decision envelope must be rerecorded",
                    stale_artifact_refs=decision.invalidation_record.affected_artifacts,
                ),
            ),
        )

        decision_events = [
            event
            for event in _load_repo_events(self.repo_root)
            if event.get("event_type") == EVOLUTION_EVENT_DECISION_RECORDED
        ]

        self.assertEqual(decision.status, EVOLUTION_ENVELOPE_STATUS_INVALIDATION)
        self.assertEqual(decision.invalidation_record.run_id, executed_run.run.run_id)
        self.assertEqual(invalidation.run_id, executed_run.run.run_id)
        self.assertEqual(invalidation.candidate_id, "candidate-blocked")
        self.assertEqual(
            invalidation.remediation_actions,
            (
                EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST,
                EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
                EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
            ),
        )
        self.assertTrue(decision_events)
        self.assertEqual(
            decision_events[-1]["data"]["envelope_status"],
            EVOLUTION_ENVELOPE_STATUS_INVALIDATION,
        )


class EvolutionSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "[event_bus]\nprovider = \"jsonl\"\n",
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)
        self.runs_root = self.repo_root / ".planning" / "evolution" / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _write_run(
        self,
        run_id: str,
        *,
        target_ids: tuple[str, ...],
        selection_mode: str = "explicit",
        task_count: int = 2,
        event_count: int = 3,
        constraint_status: str = "accepted",
        accepted: bool = True,
        fitness_status: str = "scored",
        score_delta: float | None = 0.25,
        report_markdown: str | None = None,
        failure_payload: dict[str, object] | None = None,
    ) -> Path:
        artifact_dir = self.runs_root / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "run.json").write_text(
            json.dumps(
                {
                    "run": {
                        "run_id": run_id,
                        "repo_root": str(self.repo_root),
                        "target_ids": list(target_ids),
                        "selection_mode": selection_mode,
                        "status": "planned",
                        "stage": "planned",
                    },
                    "artifact_dir": str(artifact_dir),
                    "entrypoint": "execute_evolution_run",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "dataset.json").write_text(
            json.dumps(
                {
                    "repo_root": str(self.repo_root),
                    "generated_at": "2026-04-20T00:00:00Z",
                    "event_log_path": str(self.repo_root / ".planning" / "events.jsonl"),
                    "selected_task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                    "task_traces": [],
                    "event_traces": [],
                    "task_count": task_count,
                    "event_count": event_count,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "harness_plan.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "repo_root": str(self.repo_root),
                    "created_at": "2026-04-20T00:00:00Z",
                    "isolation_mode": "task_worktree_copy",
                    "mutates_live_task_state": False,
                    "requires_branch_snapshot": True,
                    "requires_task_worktree_copy": True,
                    "requires_result_capture": True,
                    "dataset_task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                    "dataset_event_count": event_count,
                    "baseline": {
                        "evaluation_id": f"{run_id}:baseline",
                        "role": "baseline",
                        "label": "baseline",
                        "target_ids": list(target_ids),
                        "task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                        "status": "completed",
                        "metrics": {
                            "verify_pass_rate": 1.0,
                            "conformance_status": "green",
                            "drift_count": 0,
                            "unresolved_warning_count": 0,
                            "runtime_ms": 10,
                            "token_estimate": 50,
                            "operator_reviewability": "high",
                        },
                        "notes": "baseline",
                    },
                    "candidate": {
                        "evaluation_id": f"{run_id}:candidate",
                        "role": "candidate",
                        "label": "candidate",
                        "target_ids": list(target_ids),
                        "task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                        "status": "completed",
                        "metrics": {
                            "verify_pass_rate": 1.0,
                            "conformance_status": "green",
                            "drift_count": 0,
                            "unresolved_warning_count": 0,
                            "runtime_ms": 12,
                            "token_estimate": 48,
                            "operator_reviewability": "high",
                        },
                        "notes": "candidate",
                    },
                    "notes": "harness",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "constraints.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": constraint_status,
                    "accepted": accepted,
                    "warning_increase_threshold": 0,
                    "baseline_evaluation_id": f"{run_id}:baseline",
                    "candidate_evaluation_id": f"{run_id}:candidate",
                    "blocking_failure_count": 0 if accepted else 1,
                    "pending_guard_count": 0,
                    "checks": [],
                    "notes": "constraints",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "fitness.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": fitness_status,
                    "eligible_for_promotion": accepted,
                    "comparable_metric_count": 2,
                    "baseline_score": 0.62,
                    "candidate_score": 0.87,
                    "score_delta": score_delta,
                    "comparisons": [],
                    "notes": "fitness",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if report_markdown is None:
            report_markdown = (
                "# Evolution Report\n\n"
                f"- Run ID: `{run_id}`\n"
                "- Status: `ready_for_review`\n"
                "- Recommendation: `review_candidate`\n"
            )
        (artifact_dir / "report.md").write_text(report_markdown, encoding="utf-8")
        if failure_payload is not None:
            (artifact_dir / "failure.json").write_text(json.dumps(failure_payload, indent=2) + "\n", encoding="utf-8")
        return artifact_dir

    def test_load_and_render_evolution_run_surface(self) -> None:
        self._write_run(
            "EVR-surface-alpha",
            target_ids=("execution-contract-wording",),
        )

        artifacts = load_evolution_run_artifacts(self.repo_root, "EVR-surface-alpha")

        self.assertEqual(artifacts.final_stage, "report_built")
        self.assertEqual(artifacts.report_status, "ready_for_review")
        self.assertEqual(artifacts.recommendation, "review_candidate")
        self.assertIn("run.json", artifacts.available_artifacts)
        self.assertIn("report.md", artifacts.available_artifacts)
        self.assertIn("Run ID: EVR-surface-alpha", render_evolution_run_status(artifacts))
        self.assertIn("final_stage: report_built", render_evolution_run_overview(artifacts))
        self.assertIn("# Evolution Report", render_evolution_run_report(artifacts))

    def test_compare_evolution_runs_summarizes_differences(self) -> None:
        self._write_run(
            "EVR-surface-left",
            target_ids=("execution-contract-wording",),
            task_count=2,
            event_count=3,
            score_delta=0.10,
        )
        self._write_run(
            "EVR-surface-right",
            target_ids=("mcp-tool-descriptions", "execution-contract-wording"),
            task_count=4,
            event_count=7,
            score_delta=0.30,
        )

        left = load_evolution_run_artifacts(self.repo_root, "EVR-surface-left")
        right = load_evolution_run_artifacts(self.repo_root, "EVR-surface-right")
        comparison = compare_evolution_runs(left, right)

        self.assertEqual(comparison.left_run_id, "EVR-surface-left")
        self.assertEqual(comparison.right_run_id, "EVR-surface-right")
        self.assertIn("EVR-surface-left", render_evolution_run_compare(comparison))
        self.assertIn("Dataset Tasks: 2 -> 4", comparison.lines)
        self.assertIn("Fitness Score Delta: +0.10 -> +0.30", comparison.lines)

    def test_execute_surface_runs_read_only_orchestrator(self) -> None:
        self._new_task("surface-execute")
        result = execute_evolution_surface(self.repo_root, run_id="EVR-surface-execute")

        artifact_dir = self.runs_root / "EVR-surface-execute"
        self.assertTrue(result.ok)
        self.assertEqual(result.run_id, "EVR-surface-execute")
        self.assertEqual(result.resource_uri, "evolution://EVR-surface-execute/run")
        self.assertEqual(result.final_stage, "report_built")
        self.assertEqual(result.artifact_dir, str(artifact_dir.resolve()))
        self.assertIn("evolution run EVR-surface-execute", result.content)
        self.assertTrue((artifact_dir / "run.json").exists())
        self.assertTrue((artifact_dir / "report.md").exists())

    def test_execute_surface_reports_duplicate_run_id_actionably(self) -> None:
        self._new_task("surface-duplicate")
        first = execute_evolution_surface(self.repo_root, run_id="EVR-surface-duplicate")
        second = execute_evolution_surface(self.repo_root, run_id="EVR-surface-duplicate")

        self.assertTrue(first.ok)
        self.assertFalse(second.ok)
        self.assertEqual(second.run_id, "EVR-surface-duplicate")
        self.assertEqual(second.resource_uri, "evolution://EVR-surface-duplicate/run")
        self.assertEqual(second.artifact_dir, str((self.runs_root / "EVR-surface-duplicate").resolve()))
        self.assertEqual(second.error_type, "FileExistsError")
        self.assertIn("EVR-surface-duplicate", second.content)

if __name__ == "__main__":
    unittest.main()
