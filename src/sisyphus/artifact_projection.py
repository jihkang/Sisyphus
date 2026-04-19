from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import (
    ARTIFACT_STATE_CANDIDATE,
    ARTIFACT_STATE_INVALID,
    ARTIFACT_STATE_VERIFIED,
    INVARIANT_STATUS_PASSED,
    ArtifactInvariantRecord,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactRef,
    CollectionSlotBinding,
    CompositeArtifactRecord,
    FeatureChangeSlotBindings,
    NamedSlotBinding,
    TaskRunRef,
    TaskSpecRef,
    VerificationClaimRecord,
)
from .config import SisyphusConfig
from .state import load_task_record
from .strategy import sync_test_strategy_from_docs


@dataclass(frozen=True, slots=True)
class FeatureTaskArtifactProjection:
    task_id: str
    feature_id: str
    feature_change_artifact: CompositeArtifactRecord
    slot_bindings: FeatureChangeSlotBindings
    spec_artifact: ArtifactRecord
    implementation_artifact: ArtifactRecord
    test_artifacts: tuple[ArtifactRecord, ...]
    verification_claims: tuple[VerificationClaimRecord, ...]
    execution_receipts: tuple[ArtifactRecord, ...]
    task_run_refs: tuple[TaskRunRef, ...]


def project_feature_task(repo_root: Path, config: SisyphusConfig, task_id: str) -> FeatureTaskArtifactProjection:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    return project_feature_task_record(task=task, task_dir=task_file.parent)


def project_feature_task_record(task: dict, task_dir: Path) -> FeatureTaskArtifactProjection:
    if task.get("type") != "feature":
        raise ValueError(f"feature task projection supports only feature tasks, got {task.get('type')!r}")

    synced_task = sync_test_strategy_from_docs(dict(task), task_dir)
    brief_path = _require_task_doc_path(synced_task, task_dir, "brief")
    plan_path = _require_task_doc_path(synced_task, task_dir, "plan")

    feature_id = _feature_id_for(synced_task)
    spec_artifact = _build_spec_artifact(synced_task, feature_id, brief_path, plan_path)
    implementation_artifact = _build_implementation_artifact(synced_task, feature_id)
    test_artifacts = _build_test_artifacts(synced_task, feature_id)
    execution_receipts = _build_execution_receipts(synced_task, feature_id)
    task_run_refs = _build_task_run_refs(synced_task, execution_receipts)
    verification_claims = _build_verification_claims(
        task=synced_task,
        feature_id=feature_id,
        spec_artifact=spec_artifact,
        implementation_artifact=implementation_artifact,
        test_artifacts=test_artifacts,
        execution_receipts=execution_receipts,
    )
    slot_bindings = _build_slot_bindings(
        spec_artifact=spec_artifact,
        implementation_artifact=implementation_artifact,
        test_artifacts=test_artifacts,
        verification_claims=verification_claims,
        execution_receipts=execution_receipts,
    )
    feature_change_artifact = _build_feature_change_artifact(
        task=synced_task,
        feature_id=feature_id,
        spec_artifact=spec_artifact,
        implementation_artifact=implementation_artifact,
        test_artifacts=test_artifacts,
        verification_claims=verification_claims,
        execution_receipts=execution_receipts,
        slot_bindings=slot_bindings,
        task_run_refs=task_run_refs,
    )
    return FeatureTaskArtifactProjection(
        task_id=str(synced_task["id"]),
        feature_id=feature_id,
        feature_change_artifact=feature_change_artifact,
        slot_bindings=slot_bindings,
        spec_artifact=spec_artifact,
        implementation_artifact=implementation_artifact,
        test_artifacts=test_artifacts,
        verification_claims=verification_claims,
        execution_receipts=execution_receipts,
        task_run_refs=task_run_refs,
    )


def _build_spec_artifact(task: dict, feature_id: str, brief_path: Path, plan_path: Path) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=_artifact_id(task, "spec"),
        artifact_type="feature_spec",
        state=ARTIFACT_STATE_VERIFIED if task.get("verify_status") == "passed" else ARTIFACT_STATE_CANDIDATE,
        payload={
            "feature_id": feature_id,
            "task_id": str(task["id"]),
            "brief_path": brief_path.name,
            "brief_content": brief_path.read_text(encoding="utf-8"),
            "plan_path": plan_path.name,
            "plan_content": plan_path.read_text(encoding="utf-8"),
        },
        summary=f"feature spec for {task['id']}",
        lineage=ArtifactLineage(
            repo_id=str(task.get("repo_root") or ""),
            base_ref=str(task.get("base_branch") or ""),
        ),
    )


def _build_implementation_artifact(task: dict, feature_id: str) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=_artifact_id(task, "implementation"),
        artifact_type="implementation_candidate",
        state=_projected_state(task),
        payload={
            "feature_id": feature_id,
            "task_id": str(task["id"]),
            "branch": str(task.get("branch") or ""),
            "base_branch": str(task.get("base_branch") or ""),
            "workflow_phase": str(task.get("workflow_phase") or ""),
            "verify_status": str(task.get("verify_status") or ""),
        },
        summary=f"implementation candidate for {task['id']}",
        lineage=ArtifactLineage(
            repo_id=str(task.get("repo_root") or ""),
            base_ref=str(task.get("base_branch") or ""),
            parent_artifacts=(ArtifactRef(_artifact_id(task, "spec"), "feature_spec"),),
        ),
    )


def _build_test_artifacts(task: dict, feature_id: str) -> tuple[ArtifactRecord, ...]:
    artifacts: list[ArtifactRecord] = []
    strategy = task.get("test_strategy", {})
    for category, case_key in (
        ("normal", "normal_cases"),
        ("edge", "edge_cases"),
        ("exception", "exception_cases"),
    ):
        for index, case in enumerate(strategy.get(case_key, []), start=1):
            name = str(case.get("name") or "").strip()
            if not name:
                continue
            artifacts.append(
                ArtifactRecord(
                    artifact_id=_artifact_id(task, f"test-{category}-{index}"),
                    artifact_type="test_obligation",
                    state=ARTIFACT_STATE_CANDIDATE,
                    payload={
                        "feature_id": feature_id,
                        "task_id": str(task["id"]),
                        "category": category,
                        "name": name,
                        "checked": bool(case.get("checked", False)),
                    },
                    summary=f"{category} test obligation for {task['id']}",
                )
            )
    return tuple(artifacts)


def _build_execution_receipts(task: dict, feature_id: str) -> tuple[ArtifactRecord, ...]:
    receipts: list[ArtifactRecord] = []
    for index, result in enumerate(task.get("last_verify_results", []), start=1):
        receipts.append(
            ArtifactRecord(
                artifact_id=_artifact_id(task, f"receipt-{index}"),
                artifact_type="execution_receipt",
                state=ARTIFACT_STATE_VERIFIED if result.get("status") == "passed" else ARTIFACT_STATE_INVALID,
                payload={
                    "feature_id": feature_id,
                    "task_id": str(task["id"]),
                    "command": str(result.get("command") or ""),
                    "status": str(result.get("status") or ""),
                    "exit_code": result.get("exit_code"),
                    "started_at": result.get("started_at"),
                    "finished_at": result.get("finished_at"),
                    "output_excerpt": str(result.get("output_excerpt") or ""),
                },
                summary=f"verify receipt {index} for {task['id']}",
            )
        )
    return tuple(receipts)


def _build_task_run_refs(task: dict, execution_receipts: tuple[ArtifactRecord, ...]) -> tuple[TaskRunRef, ...]:
    run_refs: list[TaskRunRef] = []
    for index, result in enumerate(task.get("last_verify_results", []), start=1):
        run_refs.append(
            TaskRunRef(
                task_id=str(task["id"]),
                run_id=f"{task['id']}:verify:{index}",
                status=str(result.get("status") or "unknown"),
                receipt_locator=execution_receipts[index - 1].artifact_id,
            )
        )
    return tuple(run_refs)


def _build_verification_claims(
    *,
    task: dict,
    feature_id: str,
    spec_artifact: ArtifactRecord,
    implementation_artifact: ArtifactRecord,
    test_artifacts: tuple[ArtifactRecord, ...],
    execution_receipts: tuple[ArtifactRecord, ...],
) -> tuple[VerificationClaimRecord, ...]:
    if task.get("verify_status") != "passed":
        return ()

    dependency_refs = (
        ArtifactRef(spec_artifact.artifact_id, spec_artifact.artifact_type),
        ArtifactRef(implementation_artifact.artifact_id, implementation_artifact.artifact_type),
        *(
            ArtifactRef(artifact.artifact_id, artifact.artifact_type)
            for artifact in test_artifacts
        ),
    )
    evidence_refs = tuple(
        ArtifactRef(artifact.artifact_id, artifact.artifact_type)
        for artifact in execution_receipts
    )
    return (
        VerificationClaimRecord(
            claim_id=_artifact_id(task, "verification-claim-1"),
            claim=f"feature task {task['id']} verify flow passed for {feature_id}",
            scope="composite",
            dependency_refs=dependency_refs,
            evidence_refs=evidence_refs,
        ),
    )


def _build_slot_bindings(
    *,
    spec_artifact: ArtifactRecord,
    implementation_artifact: ArtifactRecord,
    test_artifacts: tuple[ArtifactRecord, ...],
    verification_claims: tuple[VerificationClaimRecord, ...],
    execution_receipts: tuple[ArtifactRecord, ...],
) -> FeatureChangeSlotBindings:
    return FeatureChangeSlotBindings(
        spec=NamedSlotBinding(
            slot_name="spec",
            artifact=ArtifactRef(spec_artifact.artifact_id, spec_artifact.artifact_type),
        ),
        implementation_candidates=CollectionSlotBinding(
            slot_name="implementation_candidates",
            artifacts=(
                ArtifactRef(implementation_artifact.artifact_id, implementation_artifact.artifact_type),
            ),
        ),
        selected_implementation=NamedSlotBinding(
            slot_name="selected_implementation",
            artifact=ArtifactRef(implementation_artifact.artifact_id, implementation_artifact.artifact_type),
        ),
        tests=CollectionSlotBinding(
            slot_name="tests",
            artifacts=tuple(ArtifactRef(artifact.artifact_id, artifact.artifact_type) for artifact in test_artifacts),
        ),
        verification_claims=CollectionSlotBinding(
            slot_name="verification_claims",
            artifacts=tuple(ArtifactRef(claim.claim_id, "verification_claim") for claim in verification_claims),
        ),
        execution_receipts=CollectionSlotBinding(
            slot_name="execution_receipts",
            artifacts=tuple(ArtifactRef(artifact.artifact_id, artifact.artifact_type) for artifact in execution_receipts),
        ),
    )


def _build_feature_change_artifact(
    *,
    task: dict,
    feature_id: str,
    spec_artifact: ArtifactRecord,
    implementation_artifact: ArtifactRecord,
    test_artifacts: tuple[ArtifactRecord, ...],
    verification_claims: tuple[VerificationClaimRecord, ...],
    execution_receipts: tuple[ArtifactRecord, ...],
    slot_bindings: FeatureChangeSlotBindings,
    task_run_refs: tuple[TaskRunRef, ...],
) -> CompositeArtifactRecord:
    child_artifacts = (
        ArtifactRef(spec_artifact.artifact_id, spec_artifact.artifact_type),
        ArtifactRef(implementation_artifact.artifact_id, implementation_artifact.artifact_type),
        *(ArtifactRef(artifact.artifact_id, artifact.artifact_type) for artifact in test_artifacts),
        *(ArtifactRef(claim.claim_id, "verification_claim") for claim in verification_claims),
        *(ArtifactRef(artifact.artifact_id, artifact.artifact_type) for artifact in execution_receipts),
    )
    return CompositeArtifactRecord(
        artifact_id=_artifact_id(task, "feature-change"),
        artifact_type="feature_change",
        state=_projected_state(task),
        payload={
            "feature_id": feature_id,
            "task_id": str(task["id"]),
            "branch": str(task.get("branch") or ""),
            "base_branch": str(task.get("base_branch") or ""),
            "workflow_phase": str(task.get("workflow_phase") or ""),
            "verify_status": str(task.get("verify_status") or ""),
            "slot_bindings": slot_bindings.to_dict(),
            "verification_claims": [claim.to_dict() for claim in verification_claims],
        },
        summary=f"feature change projection for {task['id']}",
        composition_rule="feature_change/v1",
        child_artifacts=child_artifacts,
        task_specs=(
            TaskSpecRef(
                task_id=str(task["id"]),
                revision=str(task.get("spec_frozen_at") or task.get("updated_at") or ""),
                doc_path=str(Path(str(task["task_dir"])) / str(task["docs"]["plan"])),
            ),
        ),
        task_runs=task_run_refs,
        lineage=ArtifactLineage(
            repo_id=str(task.get("repo_root") or ""),
            base_ref=str(task.get("base_branch") or ""),
            parent_artifacts=(
                ArtifactRef(spec_artifact.artifact_id, spec_artifact.artifact_type),
                ArtifactRef(implementation_artifact.artifact_id, implementation_artifact.artifact_type),
            ),
        ),
        evidence_refs=tuple(
            ArtifactRef(artifact.artifact_id, artifact.artifact_type)
            for artifact in execution_receipts
        ),
        invariants=(
            ArtifactInvariantRecord("same-feature-id", INVARIANT_STATUS_PASSED),
            ArtifactInvariantRecord("selected-is-candidate", INVARIANT_STATUS_PASSED),
        ),
    )


def _projected_state(task: dict) -> str:
    verify_status = str(task.get("verify_status") or "")
    if verify_status == "passed":
        return ARTIFACT_STATE_VERIFIED
    if str(task.get("status") or "") == "blocked":
        return ARTIFACT_STATE_INVALID
    return ARTIFACT_STATE_CANDIDATE


def _require_task_doc_path(task: dict, task_dir: Path, doc_key: str) -> Path:
    relative_path = task.get("docs", {}).get(doc_key)
    if not relative_path:
        raise ValueError(f"feature task projection requires docs.{doc_key}")
    path = task_dir / str(relative_path)
    if not path.exists():
        raise FileNotFoundError(f"feature task projection requires existing {relative_path}")
    return path


def _feature_id_for(task: dict) -> str:
    slug = str(task.get("slug") or "").strip()
    if not slug:
        raise ValueError("feature task projection requires a slug")
    return f"feature/{slug}"


def _artifact_id(task: dict, suffix: str) -> str:
    return f"artifact-{task['id']}-{suffix}"


__all__ = [
    "FeatureTaskArtifactProjection",
    "project_feature_task",
    "project_feature_task_record",
]
