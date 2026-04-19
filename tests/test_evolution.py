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
    EVOLUTION_DEFAULT_REVIEW_GATES,
    EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK,
    EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
    EVOLUTION_EVALUATION_STATUS_COMPLETED,
    EVOLUTION_EVALUATION_STATUS_FAILED,
    EVOLUTION_EVALUATION_STATUS_PLANNED,
    EVOLUTION_EXTENSION_STAGE_SEQUENCE,
    EVOLUTION_FAILURE_SHAPE,
    EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY,
    EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED,
    EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED,
    EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED,
    EVOLUTION_PHASE_1,
    EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
    EVOLUTION_READ_ONLY_RUN_STAGES,
    EVOLUTION_READ_ONLY_STAGE_SEQUENCE,
    EVOLUTION_STAGE_FAILED,
    EVOLUTION_STAGE_REPORT_BUILT,
    EVOLUTION_TARGET_KIND_TEXT_POLICY,
    EvolutionArtifactRef,
    EvolutionCandidateArtifact,
    EvolutionDatasetArtifact,
    EvolutionEvaluationArtifact,
    EvolutionEvaluationExecutionError,
    EvolutionEvaluationOutcome,
    EvolutionEvidenceSummary,
    EvolutionFollowupRequest,
    EvolutionFollowupRequestArtifact,
    EvolutionMaterializationError,
    EvolutionPlannedMetrics,
    EvolutionPromotionCandidate,
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
    build_sisyphus_evaluation_request,
    build_worktree_evaluation_command_plan,
    evaluate_evolution_constraints,
    evaluate_evolution_fitness,
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
)
from sisyphus.config import load_config
from sisyphus.conformance import append_conformance_log
from sisyphus.state import create_task_record, save_task_record
from sisyphus.templates import materialize_task_templates


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
            title="Request normal Sisyphus follow-up task",
            summary="handoff instead of direct mutation",
            requested_task_type="feature",
            requested_targets=("execution-contract-wording",),
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
            decision="pending_followup_execution",
            claim="candidate is eligible for reviewable handoff",
            followup_task_id="TF-123",
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


class EvolutionDatasetTests(unittest.TestCase):
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

    def _repo_snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.repo_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.repo_root.rglob("*"))
            if path.is_file() and ".planning/evolution/runs/" not in path.as_posix()
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


if __name__ == "__main__":
    unittest.main()
