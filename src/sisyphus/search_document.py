from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_evaluator import evaluate_feature_task_projection
from .artifact_projection import project_feature_task_record
from .artifact_snapshot import (
    FeatureTaskArtifactSnapshotStatus,
    build_feature_task_artifact_snapshot,
    evaluate_feature_task_artifact_snapshot_status,
    feature_task_artifact_snapshot_with_status,
    read_feature_task_artifact_snapshot,
)
from .config import SisyphusConfig
from .state import list_task_records


SEARCH_DOCUMENT_SCHEMA_VERSION = "sisyphus.search_document.v1"


@dataclass(frozen=True, slots=True)
class SearchDocument:
    document_id: str
    source_type: str
    source_ref: str
    title: str
    content: str
    task_id: str | None = None
    task_type: str | None = None
    task_slug: str | None = None
    doc_key: str | None = None
    doc_path: str | None = None
    artifact_id: str | None = None
    artifact_type: str | None = None
    freshness_status: str | None = None
    updated_at: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    fingerprint: str = ""
    schema_version: str = SEARCH_DOCUMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _require_string(self.document_id, "document_id"))
        object.__setattr__(self, "source_type", _require_string(self.source_type, "source_type"))
        object.__setattr__(self, "source_ref", _require_string(self.source_ref, "source_ref"))
        object.__setattr__(self, "title", _require_string(self.title, "title"))
        object.__setattr__(self, "content", _require_string(self.content, "content"))
        object.__setattr__(self, "task_id", _optional_string(self.task_id))
        object.__setattr__(self, "task_type", _optional_string(self.task_type))
        object.__setattr__(self, "task_slug", _optional_string(self.task_slug))
        object.__setattr__(self, "doc_key", _optional_string(self.doc_key))
        object.__setattr__(self, "doc_path", _optional_string(self.doc_path))
        object.__setattr__(self, "artifact_id", _optional_string(self.artifact_id))
        object.__setattr__(self, "artifact_type", _optional_string(self.artifact_type))
        object.__setattr__(self, "freshness_status", _optional_string(self.freshness_status))
        object.__setattr__(self, "updated_at", _optional_string(self.updated_at))
        object.__setattr__(self, "metadata", {str(key): _json_safe(value) for key, value in self.metadata.items()})
        object.__setattr__(self, "schema_version", SEARCH_DOCUMENT_SCHEMA_VERSION)
        fingerprint = _optional_string(self.fingerprint) or fingerprint_search_document_payload(_fingerprint_payload(self))
        object.__setattr__(self, "fingerprint", fingerprint)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "title": self.title,
            "content": self.content,
            "metadata": _json_safe(self.metadata),
            "fingerprint": self.fingerprint,
        }
        for key in (
            "task_id",
            "task_type",
            "task_slug",
            "doc_key",
            "doc_path",
            "artifact_id",
            "artifact_type",
            "freshness_status",
            "updated_at",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> SearchDocument:
        schema_version = str(raw.get("schema_version") or "").strip()
        if schema_version != SEARCH_DOCUMENT_SCHEMA_VERSION:
            raise ValueError(
                f"search document schema_version must be {SEARCH_DOCUMENT_SCHEMA_VERSION!r}, got {schema_version!r}"
            )
        metadata = raw.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, Mapping):
            raise ValueError("search document metadata must be an object")
        return cls(
            document_id=_require_string(raw.get("document_id"), "document_id"),
            source_type=_require_string(raw.get("source_type"), "source_type"),
            source_ref=_require_string(raw.get("source_ref"), "source_ref"),
            title=_require_string(raw.get("title"), "title"),
            content=_require_string(raw.get("content"), "content"),
            task_id=_optional_string(raw.get("task_id")),
            task_type=_optional_string(raw.get("task_type")),
            task_slug=_optional_string(raw.get("task_slug")),
            doc_key=_optional_string(raw.get("doc_key")),
            doc_path=_optional_string(raw.get("doc_path")),
            artifact_id=_optional_string(raw.get("artifact_id")),
            artifact_type=_optional_string(raw.get("artifact_type")),
            freshness_status=_optional_string(raw.get("freshness_status")),
            updated_at=_optional_string(raw.get("updated_at")),
            metadata={str(key): value for key, value in metadata.items()},
            fingerprint=_require_string(raw.get("fingerprint"), "fingerprint"),
        )


def project_repo_search_documents(repo_root: Path, config: SisyphusConfig) -> tuple[SearchDocument, ...]:
    documents: list[SearchDocument] = []
    for task in sorted(list_task_records(repo_root=repo_root, task_dir_name=config.task_dir), key=lambda item: str(item.get("id") or "")):
        task_dir = repo_root / str(task["task_dir"])
        documents.extend(project_task_search_documents(task, task_dir))
    return tuple(sorted(documents, key=lambda document: document.document_id))


def project_task_search_documents(task: Mapping[str, object], task_dir: Path) -> tuple[SearchDocument, ...]:
    normalized_task = dict(task)
    documents: list[SearchDocument] = []
    documents.extend(_project_task_doc_documents(normalized_task, task_dir))
    documents.extend(_project_feature_artifact_documents(normalized_task, task_dir))
    return tuple(sorted(documents, key=lambda document: document.document_id))


def fingerprint_search_document_payload(payload: Mapping[str, object]) -> str:
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _project_task_doc_documents(task: dict, task_dir: Path) -> list[SearchDocument]:
    documents: list[SearchDocument] = []
    docs = task.get("docs", {})
    if not isinstance(docs, Mapping):
        return documents

    for doc_key in ("brief", "plan", "fix_plan", "verify", "log"):
        relative_path = _optional_string(docs.get(doc_key))
        if relative_path is None:
            continue
        path = task_dir / relative_path
        if not path.exists() or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            continue
        task_id = str(task.get("id") or "")
        resource_name = "plan" if doc_key == "fix_plan" else doc_key
        source_ref = f"task://{task_id}/{resource_name}"
        documents.append(
            _make_document(
                source_type="task_doc",
                source_ref=source_ref,
                title=f"{task_id} {doc_key.upper()} {task.get('slug') or ''}".strip(),
                content=content,
                task=task,
                doc_key=doc_key,
                doc_path=str(Path(str(task.get("task_dir") or "")) / relative_path),
                metadata={
                    "plan_status": task.get("plan_status"),
                    "spec_status": task.get("spec_status"),
                    "verify_status": task.get("verify_status"),
                    "workflow_phase": task.get("workflow_phase"),
                },
            )
        )
    return documents


def _project_feature_artifact_documents(task: dict, task_dir: Path) -> list[SearchDocument]:
    if task.get("type") != "feature":
        return []

    snapshot = _load_or_build_feature_snapshot(task, task_dir)
    if snapshot is None:
        return []

    task_id = str(task.get("id") or "")
    snapshot_status = snapshot.get("snapshot_status", {})
    freshness_status = None
    if isinstance(snapshot_status, Mapping):
        freshness_status = _optional_string(snapshot_status.get("status"))

    documents = [
        _make_document(
            source_type="artifact_snapshot",
            source_ref=f"task://{task_id}/artifact-graph",
            title=f"{task_id} feature artifact snapshot",
            content=_snapshot_content(snapshot),
            task=task,
            artifact_id=_optional_string(snapshot.get("source_artifact_id")),
            artifact_type="feature_change",
            freshness_status=freshness_status,
            metadata={
                "feature_id": snapshot.get("feature_id"),
                "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
                "snapshot_status": snapshot_status,
            },
        )
    ]

    claims = snapshot.get("verification_claims", [])
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, Mapping):
                continue
            claim_id = _optional_string(claim.get("claim_id"))
            if claim_id is None:
                continue
            documents.append(
                _make_document(
                    source_type="verification_claim",
                    source_ref=f"task://{task_id}/verification-claims#{claim_id}",
                    title=f"{task_id} verification claim {claim.get('scope') or claim_id}",
                    content=_verification_claim_content(claim),
                    task=task,
                    artifact_id=claim_id,
                    artifact_type="verification_claim",
                    freshness_status=freshness_status,
                    metadata={
                        "scope": claim.get("scope"),
                        "status": claim.get("status"),
                        "dependency_refs": claim.get("dependency_refs", []),
                        "evidence_refs": claim.get("evidence_refs", []),
                        "based_on_input_fingerprint": claim.get("based_on_input_fingerprint"),
                    },
                )
            )
    return documents


def _load_or_build_feature_snapshot(task: dict, task_dir: Path) -> dict[str, object] | None:
    snapshot = read_feature_task_artifact_snapshot(task_dir)
    if snapshot is not None:
        try:
            status = evaluate_feature_task_artifact_snapshot_status(snapshot, task=dict(task), task_dir=task_dir)
        except Exception as exc:
            status = FeatureTaskArtifactSnapshotStatus(
                status="unavailable",
                fingerprint=_optional_string(snapshot.get("snapshot_fingerprint")),
                reason=str(exc),
            )
        return feature_task_artifact_snapshot_with_status(snapshot, status)

    try:
        projection = project_feature_task_record(dict(task), task_dir)
        evaluation = evaluate_feature_task_projection(projection)
        return build_feature_task_artifact_snapshot(projection, evaluation)
    except Exception:
        return None


def _make_document(
    *,
    source_type: str,
    source_ref: str,
    title: str,
    content: str,
    task: Mapping[str, object],
    doc_key: str | None = None,
    doc_path: str | None = None,
    artifact_id: str | None = None,
    artifact_type: str | None = None,
    freshness_status: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> SearchDocument:
    document_id = f"searchdoc:{source_ref}"
    return SearchDocument(
        document_id=document_id,
        source_type=source_type,
        source_ref=source_ref,
        title=title,
        content=content,
        task_id=_optional_string(task.get("id")),
        task_type=_optional_string(task.get("type")),
        task_slug=_optional_string(task.get("slug")),
        doc_key=doc_key,
        doc_path=doc_path,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        freshness_status=freshness_status,
        updated_at=_optional_string(task.get("updated_at")),
        metadata=dict(metadata or {}),
    )


def _snapshot_content(snapshot: Mapping[str, object]) -> str:
    evaluation = snapshot.get("evaluation", {})
    promotion: object = {}
    invalidation: object = {}
    derived_state = None
    if isinstance(evaluation, Mapping):
        promotion = evaluation.get("promotion", {})
        invalidation = evaluation.get("invalidation", {})
        derived_state = evaluation.get("derived_state")

    lines = [
        "Feature artifact snapshot",
        f"task_id: {snapshot.get('task_id')}",
        f"feature_id: {snapshot.get('feature_id')}",
        f"source_artifact_id: {snapshot.get('source_artifact_id')}",
        f"snapshot_status: {_compact_json(snapshot.get('snapshot_status', {}))}",
        f"derived_state: {derived_state}",
        f"promotion: {_compact_json(promotion)}",
        f"invalidation: {_compact_json(invalidation)}",
    ]
    return "\n".join(lines)


def _verification_claim_content(claim: Mapping[str, object]) -> str:
    lines = [
        "Verification claim",
        f"claim_id: {claim.get('claim_id')}",
        f"scope: {claim.get('scope')}",
        f"status: {claim.get('status')}",
        f"claim: {claim.get('claim')}",
        f"dependency_refs: {_compact_json(claim.get('dependency_refs', []))}",
        f"evidence_refs: {_compact_json(claim.get('evidence_refs', []))}",
        f"based_on_input_fingerprint: {claim.get('based_on_input_fingerprint')}",
    ]
    return "\n".join(lines)


def _fingerprint_payload(document: SearchDocument) -> dict[str, object]:
    return {
        "source_type": document.source_type,
        "source_ref": document.source_ref,
        "title": document.title,
        "content": document.content,
        "task_id": document.task_id,
        "task_type": document.task_type,
        "task_slug": document.task_slug,
        "doc_key": document.doc_key,
        "doc_path": document.doc_path,
        "artifact_id": document.artifact_id,
        "artifact_type": document.artifact_type,
        "freshness_status": document.freshness_status,
        "updated_at": document.updated_at,
        "metadata": document.metadata,
    }


def _compact_json(value: object) -> str:
    return json.dumps(_json_safe(value), separators=(",", ":"), sort_keys=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _require_string(value: object, name: str) -> str:
    normalized = _optional_string(value)
    if normalized is None:
        raise ValueError(f"{name} must be a non-empty string")
    return normalized


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


__all__ = [
    "SEARCH_DOCUMENT_SCHEMA_VERSION",
    "SearchDocument",
    "fingerprint_search_document_payload",
    "project_repo_search_documents",
    "project_task_search_documents",
]
