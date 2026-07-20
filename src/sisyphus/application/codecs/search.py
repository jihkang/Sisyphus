from __future__ import annotations

from collections.abc import Mapping

from ..search.models import (
    SEARCH_DOCUMENT_SCHEMA_VERSION,
    SearchDocument,
    SearchIndexRebuildResult,
)
from ..search.retrieval import RetrievalResult


def encode_search_index_rebuild_result(
    value: SearchIndexRebuildResult,
) -> dict[str, object]:
    return {
        "index_path": str(value.index_path),
        "document_count": value.document_count,
        "changed": value.changed,
    }


def encode_search_document(value: SearchDocument) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": value.schema_version,
        "document_id": value.document_id,
        "source_type": value.source_type,
        "source_ref": value.source_ref,
        "title": value.title,
        "content": value.content,
        "metadata": _json_safe(value.metadata),
        "fingerprint": value.fingerprint,
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
        item = getattr(value, key)
        if item is not None:
            data[key] = item
    return data


def decode_search_document(raw: Mapping[str, object]) -> SearchDocument:
    schema_version = str(raw.get("schema_version") or "").strip()
    if schema_version != SEARCH_DOCUMENT_SCHEMA_VERSION:
        raise ValueError(
            "search document schema_version must be "
            f"{SEARCH_DOCUMENT_SCHEMA_VERSION!r}, got {schema_version!r}"
        )
    metadata = raw.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise ValueError("search document metadata must be an object")
    return SearchDocument(
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


def encode_retrieval_result(value: RetrievalResult) -> dict[str, object]:
    return {
        "rank": value.rank,
        "score": value.score,
        "matched_terms": list(value.matched_terms),
        "excerpt": value.excerpt,
        "document": encode_search_document(value.document),
    }


def _json_safe(value: object) -> object:
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
    "decode_search_document",
    "encode_retrieval_result",
    "encode_search_document",
    "encode_search_index_rebuild_result",
]
