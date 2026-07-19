from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ...application.ports.artifact_queries import FeatureArtifactReadModel
from ...artifact_evaluator import evaluate_feature_task_projection
from ...artifact_projection import project_feature_task_record
from ...artifact_snapshot import (
    build_feature_task_artifact_snapshot,
    evaluate_feature_task_artifact_snapshot_status,
    feature_task_artifact_snapshot_with_status,
    read_feature_task_artifact_snapshot,
)
from ..obligations.runtime import (
    build_feature_change_compiled_obligation_queue,
    read_feature_change_obligation_queue,
)


class RepositoryFeatureArtifactQueries:
    def read_snapshot(
        self,
        task: Mapping[str, object],
        task_dir: Path,
    ) -> Mapping[str, object] | None:
        snapshot = read_feature_task_artifact_snapshot(task_dir)
        if snapshot is None:
            return None
        status = evaluate_feature_task_artifact_snapshot_status(
            snapshot,
            task=dict(task),
            task_dir=task_dir,
        )
        return feature_task_artifact_snapshot_with_status(snapshot, status)

    def project_current(
        self,
        task: Mapping[str, object],
        task_dir: Path,
        *,
        include_compiled_obligations: bool,
    ) -> FeatureArtifactReadModel:
        projection = project_feature_task_record(dict(task), task_dir)
        evaluation = evaluate_feature_task_projection(projection)
        obligations = (
            build_feature_change_compiled_obligation_queue(projection, evaluation)
            if include_compiled_obligations
            else None
        )
        return FeatureArtifactReadModel(
            task_id=projection.task_id,
            feature_id=projection.feature_id,
            artifact_graph=build_feature_task_artifact_snapshot(projection, evaluation),
            slot_bindings=projection.slot_bindings.to_dict(),
            verification_claims=tuple(claim.to_dict() for claim in projection.verification_claims),
            promotion=evaluation.promotion.to_dict(),
            invalidation=evaluation.invalidation.to_dict(),
            derived_state=evaluation.derived_state,
            compiled_obligations=obligations,
        )

    def read_compiled_obligations(
        self,
        task_dir: Path,
    ) -> Mapping[str, object] | None:
        return read_feature_change_obligation_queue(task_dir)


__all__ = ["RepositoryFeatureArtifactQueries"]
