from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any


SEARCH_DOCUMENT_SCHEMA_VERSION = "sisyphus.search_document.v1"


class SearchIndexError(RuntimeError):
    """Raised when a persisted search index cannot be read safely."""


@dataclass(frozen=True, slots=True)
class SearchIndexRebuildResult:
    index_path: Path
    document_count: int
    changed: bool

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
        object.__setattr__(
            self,
            "metadata",
            {str(key): _json_safe(value) for key, value in self.metadata.items()},
        )
        object.__setattr__(self, "schema_version", SEARCH_DOCUMENT_SCHEMA_VERSION)
        fingerprint = _optional_string(self.fingerprint) or fingerprint_search_document_payload(
            _fingerprint_payload(self)
        )
        object.__setattr__(self, "fingerprint", fingerprint)

def fingerprint_search_document_payload(payload: Mapping[str, object]) -> str:
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


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
    "SearchIndexError",
    "SearchIndexRebuildResult",
    "SearchDocument",
    "fingerprint_search_document_payload",
]
