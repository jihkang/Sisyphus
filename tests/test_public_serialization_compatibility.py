from __future__ import annotations

import json
import unittest

import sisyphus.action_space as action_space
import sisyphus.artifact_evaluator as artifact_evaluator
import sisyphus.artifact_snapshot as artifact_snapshot
import sisyphus.artifacts as artifacts
import sisyphus.benchmark as benchmark
import sisyphus.dsl as dsl
import sisyphus.episode_trace as episode_trace
import sisyphus.eval.loop as eval_loop
import sisyphus.events as events
import sisyphus.inbox as inbox
import sisyphus.retrieval as retrieval
import sisyphus.search_document as search_document
import sisyphus.search_index as search_index
import sisyphus.test_first as test_first
from sisyphus.providers import benchmark as provider_benchmark
from sisyphus.providers import local_agent


class PublicSerializationCompatibilityTests(unittest.TestCase):
    def test_legacy_methods_are_available_only_through_public_surfaces(self) -> None:
        expected_methods = {
            action_space.ActionSpec: {"to_dict"},
            artifact_evaluator.ArtifactPromotionDecision: {"to_dict"},
            artifact_evaluator.FeatureChangeEvaluation: {"to_dict"},
            artifact_evaluator.InvalidationRecord: {"to_dict"},
            artifact_snapshot.FeatureTaskArtifactSnapshotStatus: {"to_dict"},
            artifacts.ArtifactInvariantRecord: {"from_dict", "to_dict"},
            artifacts.ArtifactLineage: {"from_dict", "to_dict"},
            artifacts.ArtifactRecord: {"from_dict", "to_dict"},
            artifacts.ArtifactRef: {"from_dict", "to_dict"},
            artifacts.CollectionSlotBinding: {"from_dict", "to_dict"},
            artifacts.CompositeArtifactRecord: {"from_dict", "to_dict"},
            artifacts.FeatureChangeSlotBindings: {"from_dict", "to_dict"},
            artifacts.NamedSlotBinding: {"from_dict", "to_dict"},
            artifacts.TaskRunRef: {"from_dict", "to_dict"},
            artifacts.TaskSpecRef: {"from_dict", "to_dict"},
            artifacts.VerificationClaimRecord: {"from_dict", "to_dict"},
            benchmark.BenchmarkRunResult: {"to_dict"},
            dsl.CompiledObligation: {"from_dict", "to_dict"},
            dsl.ExecutionPolicy: {"from_dict", "to_dict"},
            dsl.InputContract: {"from_dict", "to_dict"},
            dsl.MaterializedInputSet: {"from_dict", "to_dict"},
            dsl.ObligationIntent: {"from_dict", "to_dict"},
            dsl.ObligationSpec: {"from_dict", "to_dict"},
            dsl.ProducedArtifactSpec: {"from_dict", "to_dict"},
            dsl.ProtocolSpec: {"from_dict", "to_dict"},
            dsl.RefSelector: {"from_dict", "to_dict"},
            episode_trace.EpisodeStep: {"to_dict"},
            eval_loop.EvalLoopResult: {"to_dict"},
            events.EventEnvelope: {"to_dict", "to_json"},
            inbox.ChangedFile: {"from_dict", "to_dict"},
            inbox.ConversationPayload: {"from_dict", "to_dict"},
            inbox.PullRequestMergedPayload: {"from_dict", "to_dict"},
            inbox.InboxEvent: {"from_dict", "to_dict"},
            provider_benchmark.LocalAgentBenchmarkCaseResult: {"to_dict"},
            provider_benchmark.LocalAgentBenchmarkRunResult: {"to_dict"},
            local_agent.LocalAgentRunResult: {"to_dict"},
            retrieval.RetrievalResult: {"to_dict"},
            search_document.SearchDocument: {"from_dict", "to_dict"},
            search_index.SearchIndexRebuildResult: {"to_dict"},
            test_first.TestFirstEvaluation: {"to_dict"},
            test_first.TestFirstPhaseEvent: {"to_dict"},
        }

        for model, methods in expected_methods.items():
            for method in methods:
                with self.subTest(model=model.__name__, method=method):
                    self.assertTrue(callable(getattr(model, method, None)))

    def test_artifact_and_dsl_methods_round_trip_through_canonical_codecs(self) -> None:
        reference = artifacts.ArtifactRef(
            artifact_id="artifact-1",
            artifact_type="evidence",
            revision="rev-1",
        )
        selector = dsl.RefSelector("slot://spec#acceptance_criteria")

        self.assertEqual(artifacts.ArtifactRef.from_dict(reference.to_dict()), reference)
        self.assertEqual(dsl.RefSelector.from_dict(selector.to_dict()), selector)

    def test_inbox_methods_round_trip_through_strict_boundary_codecs(self) -> None:
        changed_file = inbox.ChangedFile.from_dict(
            {"path": "src/example.py", "status": "modified"},
            field="changed_files[0]",
        )

        self.assertEqual(
            changed_file.to_dict(),
            {
                "path": "src/example.py",
                "status": "modified",
            },
        )

    def test_event_json_and_provider_result_shapes_match_legacy_contracts(self) -> None:
        envelope = events.new_event_envelope(
            "task.created",
            data={"task_id": "TF-1"},
            event_id="evt-1",
        )
        run = local_agent.LocalAgentRunResult(
            status="completed",
            summary="done",
            error=None,
            observation_hash="sha256:observation",
            request_digest="sha256:request",
            started_at="2026-07-20T00:00:00Z",
            finished_at="2026-07-20T00:00:01Z",
            action_count=1,
            protocol_error_count=0,
            blocked_action_count=0,
            compaction_count=1,
            completion_facts={"completion_ready": True},
            events=(),
        )
        case = provider_benchmark.LocalAgentBenchmarkCaseResult(
            fixture_id="fixture-1",
            title="Fixture",
            kind="coding",
            passed=True,
            reason="passed",
            status="completed",
            terminal_finish=True,
            completion_ready=True,
            expected_changed_paths=("src/example.py",),
            actual_changed_paths=("src/example.py",),
            action_count=1,
            protocol_error_count=0,
            blocked_action_count=0,
            compaction_count=1,
            duration_ms=10,
        )
        benchmark_run = provider_benchmark.LocalAgentBenchmarkRunResult(
            provider_profile={"provider": "local", "model": "test"},
            started_at="2026-07-20T00:00:00Z",
            finished_at="2026-07-20T00:00:01Z",
            cases=(case,),
        )

        self.assertEqual(json.loads(envelope.to_json()), envelope.to_dict())
        self.assertEqual(run.to_dict()["completion_facts"], {"completion_ready": True})
        self.assertEqual(case.to_dict()["actual_changed_paths"], ["src/example.py"])
        self.assertEqual(benchmark_run.to_dict()["summary"]["passed_count"], 1)

    def test_domain_package_repository_exports_preserve_identity(self) -> None:
        import sisyphus.domain.agent as agent_package
        import sisyphus.domain.task as task_package
        from sisyphus.domain.agent import repository as agent_shim
        from sisyphus.domain.task import repository as task_shim

        for package, shim in (
            (agent_package, agent_shim),
            (task_package, task_shim),
        ):
            for name in shim.__all__:
                with self.subTest(package=package.__name__, name=name):
                    self.assertIs(getattr(package, name), getattr(shim, name))


if __name__ == "__main__":
    unittest.main()
