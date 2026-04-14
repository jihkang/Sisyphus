from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import sys
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from taskflow.evolution import (
    EVOLUTION_EVALUATION_STATUS_PLANNED,
    EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY,
    EVOLUTION_PHASE_1,
    EVOLUTION_TARGET_KIND_TEXT_POLICY,
    EvolutionPlannedMetrics,
    build_evolution_dataset,
    build_evolution_report,
    evaluate_evolution_constraints,
    evaluate_evolution_fitness,
    get_evolution_target,
    list_evolution_targets,
    plan_evolution_harness,
    plan_evolution_run,
)
from taskflow.config import load_config
from taskflow.conformance import append_conformance_log
from taskflow.state import create_task_record, save_task_record
from taskflow.templates import materialize_task_templates


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
        self.assertEqual(run.status, "planned")
        self.assertEqual(run.dataset_status, "not_built")
        self.assertFalse(run.mutates_live_task_state)
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
        self.assertIn("execution not implemented", plan.baseline.notes)
        self.assertIn("future work", plan.notes)

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


if __name__ == "__main__":
    unittest.main()
