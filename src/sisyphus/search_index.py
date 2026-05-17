from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .config import SisyphusConfig
from .search_document import SearchDocument, project_repo_search_documents


DEFAULT_SEARCH_INDEX_PATH = Path(".planning") / "search" / "index.jsonl"


class SearchIndexError(RuntimeError):
    """Raised when a persisted search index cannot be read safely."""


@dataclass(frozen=True, slots=True)
class SearchIndexRebuildResult:
    index_path: Path
    document_count: int
    changed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "index_path": str(self.index_path),
            "document_count": self.document_count,
            "changed": self.changed,
        }


def resolve_search_index_path(repo_root: Path, index_path: str | Path | None = None) -> Path:
    if index_path is None:
        return repo_root / DEFAULT_SEARCH_INDEX_PATH
    path = Path(index_path)
    if path.is_absolute():
        return path
    return repo_root / path


def rebuild_search_index(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    index_path: str | Path | None = None,
) -> SearchIndexRebuildResult:
    resolved_path = resolve_search_index_path(repo_root, index_path)
    documents = project_repo_search_documents(repo_root, config)
    rendered = "".join(
        json.dumps(_json_safe(document.to_dict()), separators=(",", ":"), sort_keys=True) + "\n"
        for document in documents
    )
    changed = _write_text_if_changed(resolved_path, rendered)
    return SearchIndexRebuildResult(
        index_path=resolved_path,
        document_count=len(documents),
        changed=changed,
    )


def read_search_index(repo_root: Path, *, index_path: str | Path | None = None) -> tuple[SearchDocument, ...]:
    resolved_path = resolve_search_index_path(repo_root, index_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"search index not found: {resolved_path}")

    documents: list[SearchDocument] = []
    for line_number, line in enumerate(resolved_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SearchIndexError(f"malformed search index JSONL at {resolved_path}:{line_number}: {exc}") from exc
        if not isinstance(raw, dict):
            raise SearchIndexError(f"search index line must decode to an object at {resolved_path}:{line_number}")
        try:
            documents.append(SearchDocument.from_dict(raw))
        except Exception as exc:
            raise SearchIndexError(f"invalid search document at {resolved_path}:{line_number}: {exc}") from exc
    return tuple(sorted(documents, key=lambda document: document.document_id))


def search_index_status(repo_root: Path, *, index_path: str | Path | None = None) -> dict[str, object]:
    resolved_path = resolve_search_index_path(repo_root, index_path)
    if not resolved_path.exists():
        return {
            "status": "missing",
            "index_path": str(resolved_path),
            "document_count": 0,
        }
    try:
        documents = read_search_index(repo_root, index_path=resolved_path)
    except SearchIndexError as exc:
        return {
            "status": "malformed",
            "index_path": str(resolved_path),
            "document_count": 0,
            "error": str(exc),
        }
    return {
        "status": "ready",
        "index_path": str(resolved_path),
        "document_count": len(documents),
    }


def _write_text_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "DEFAULT_SEARCH_INDEX_PATH",
    "SearchIndexError",
    "SearchIndexRebuildResult",
    "read_search_index",
    "rebuild_search_index",
    "resolve_search_index_path",
    "search_index_status",
]
