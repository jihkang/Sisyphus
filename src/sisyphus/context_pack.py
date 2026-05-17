from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import SisyphusConfig
from .events import utc_now
from .retrieval import RetrievalResult, retrieve_documents
from .search_index import read_search_index, rebuild_search_index


CONTEXT_PACK_SCHEMA_VERSION = "sisyphus.context_pack.v1"
DEFAULT_CONTEXT_PACK_DIR = Path(".planning") / "context-packs"
DEFAULT_CONTEXT_PACK_LIMIT = 5
DEFAULT_CONTEXT_PACK_EXCERPT_CHARS = 800


def build_context_pack(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    query: str,
    limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
    max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    rebuild_if_missing: bool = True,
) -> dict[str, object]:
    try:
        documents = read_search_index(repo_root)
    except FileNotFoundError:
        if not rebuild_if_missing:
            raise
        rebuild_search_index(repo_root, config)
        documents = read_search_index(repo_root)

    results = retrieve_documents(
        query,
        documents,
        limit=limit,
        excerpt_chars=max_excerpt_chars,
    )
    items = [_context_item_from_result(result, max_excerpt_chars=max_excerpt_chars) for result in results]
    fingerprint = fingerprint_context_pack_payload(
        {
            "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
            "query": query,
            "limit": limit,
            "max_excerpt_chars": max_excerpt_chars,
            "items": items,
        }
    )
    pack_id = f"context-pack-{fingerprint.split(':', 1)[1][:16]}"
    return {
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "pack_id": pack_id,
        "query": query,
        "built_at": utc_now(),
        "limit": limit,
        "max_excerpt_chars": max_excerpt_chars,
        "result_count": len(items),
        "items": items,
        "fingerprint": fingerprint,
    }


def build_and_persist_context_pack(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    query: str,
    limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
    max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    rebuild_if_missing: bool = True,
) -> tuple[dict[str, object], Path]:
    pack = build_context_pack(
        repo_root,
        config,
        query=query,
        limit=limit,
        max_excerpt_chars=max_excerpt_chars,
        rebuild_if_missing=rebuild_if_missing,
    )
    path = persist_context_pack(repo_root, pack)
    return pack, path


def persist_context_pack(repo_root: Path, pack: Mapping[str, object]) -> Path:
    pack_id = str(pack.get("pack_id") or "").strip()
    if not pack_id:
        raise ValueError("context pack requires pack_id before persistence")
    path = repo_root / DEFAULT_CONTEXT_PACK_DIR / f"{pack_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(dict(pack)), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_context_pack(repo_root: Path, pack_id: str) -> dict[str, object]:
    normalized_pack_id = pack_id.strip()
    if not normalized_pack_id:
        raise ValueError("context pack id must be non-empty")
    path = repo_root / DEFAULT_CONTEXT_PACK_DIR / f"{normalized_pack_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"context pack not found: {normalized_pack_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"context pack must be an object: {path}")
    schema_version = str(raw.get("schema_version") or "")
    if schema_version != CONTEXT_PACK_SCHEMA_VERSION:
        raise ValueError(f"context pack schema_version must be {CONTEXT_PACK_SCHEMA_VERSION!r}, got {schema_version!r}")
    return {str(key): value for key, value in raw.items()}


def fingerprint_context_pack_payload(payload: Mapping[str, object]) -> str:
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _context_item_from_result(result: RetrievalResult, *, max_excerpt_chars: int) -> dict[str, object]:
    document = result.document
    excerpt = result.excerpt
    if len(excerpt) > max_excerpt_chars:
        excerpt = f"{excerpt[: max(max_excerpt_chars - 3, 0)].rstrip()}..."
    return {
        "rank": result.rank,
        "score": result.score,
        "matched_terms": list(result.matched_terms),
        "source_ref": document.source_ref,
        "source_type": document.source_type,
        "document_id": document.document_id,
        "document_fingerprint": document.fingerprint,
        "task_id": document.task_id,
        "task_type": document.task_type,
        "task_slug": document.task_slug,
        "title": document.title,
        "excerpt": excerpt,
        "freshness_status": document.freshness_status,
        "artifact_id": document.artifact_id,
        "artifact_type": document.artifact_type,
        "metadata": document.metadata,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "CONTEXT_PACK_SCHEMA_VERSION",
    "DEFAULT_CONTEXT_PACK_DIR",
    "DEFAULT_CONTEXT_PACK_EXCERPT_CHARS",
    "DEFAULT_CONTEXT_PACK_LIMIT",
    "build_and_persist_context_pack",
    "build_context_pack",
    "fingerprint_context_pack_payload",
    "persist_context_pack",
    "read_context_pack",
]
