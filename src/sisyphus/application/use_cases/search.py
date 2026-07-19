from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from ..ports.clock import ClockPort
from ..ports.search import ContextPackStorePort, SearchIndexPort
from ..search.models import SearchDocument, SearchIndexRebuildResult
from ..search.retrieval import RetrievalResult, retrieve_documents


CONTEXT_PACK_SCHEMA_VERSION = "sisyphus.context_pack.v1"
EXECUTION_CONTEXT_PACK_PURPOSE = "workflow_execution_input"
DEFAULT_CONTEXT_PACK_LIMIT = 5
DEFAULT_CONTEXT_PACK_EXCERPT_CHARS = 800
DEFAULT_CONTEXT_QUERY_CHARS = 4000


@dataclass(slots=True)
class SearchService:
    index: SearchIndexPort
    packs: ContextPackStorePort
    clock: ClockPort

    def rebuild_index(self) -> SearchIndexRebuildResult:
        return self.index.rebuild()

    def read_index(self) -> tuple[SearchDocument, ...]:
        return self.index.read()

    def search(
        self,
        query: str,
        *,
        limit: int,
        rebuild_if_missing: bool = False,
    ) -> tuple[RetrievalResult, ...]:
        documents = self._read_documents(rebuild_if_missing=rebuild_if_missing)
        return retrieve_documents(query, documents, limit=limit)

    def index_status(self) -> dict[str, object]:
        return self.index.status()

    def build_context_pack(
        self,
        *,
        query: str,
        limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
        max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
        rebuild_if_missing: bool = True,
        exclude_task_ids: list[str] | tuple[str, ...] | None = None,
        source_task_id: str | None = None,
        purpose: str | None = None,
    ) -> dict[str, object]:
        documents = self._read_documents(rebuild_if_missing=rebuild_if_missing)
        excluded_task_ids = tuple(
            sorted(
                {
                    str(task_id)
                    for task_id in exclude_task_ids or []
                    if str(task_id).strip()
                }
            )
        )
        candidates = tuple(
            document
            for document in documents
            if document.task_id is None or document.task_id not in excluded_task_ids
        )
        results = retrieve_documents(
            query,
            candidates,
            limit=limit,
            excerpt_chars=max_excerpt_chars,
        )
        items = [
            _context_item_from_result(result, max_excerpt_chars=max_excerpt_chars)
            for result in results
        ]
        fingerprint = fingerprint_context_pack_payload(
            {
                "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
                "query": query,
                "limit": limit,
                "max_excerpt_chars": max_excerpt_chars,
                "source_task_id": source_task_id,
                "purpose": purpose,
                "excluded_task_ids": excluded_task_ids,
                "items": items,
            }
        )
        return {
            "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
            "pack_id": f"context-pack-{fingerprint.split(':', 1)[1][:16]}",
            "query": query,
            "built_at": self.clock.now(),
            "source_task_id": source_task_id,
            "purpose": purpose,
            "excluded_task_ids": list(excluded_task_ids),
            "index_document_count": len(documents),
            "candidate_document_count": len(candidates),
            "limit": limit,
            "max_excerpt_chars": max_excerpt_chars,
            "result_count": len(items),
            "items": items,
            "fingerprint": fingerprint,
        }

    def build_and_persist_context_pack(
        self,
        *,
        query: str,
        limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
        max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
        rebuild_if_missing: bool = True,
        exclude_task_ids: list[str] | tuple[str, ...] | None = None,
        source_task_id: str | None = None,
        purpose: str | None = None,
    ) -> tuple[dict[str, object], Path]:
        pack = self.build_context_pack(
            query=query,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
            rebuild_if_missing=rebuild_if_missing,
            exclude_task_ids=exclude_task_ids,
            source_task_id=source_task_id,
            purpose=purpose,
        )
        return pack, self.packs.write(pack)

    def build_task_execution_context_pack(
        self,
        *,
        task: Mapping[str, object],
        docs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
        max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
        rebuild_if_missing: bool = True,
    ) -> tuple[dict[str, object], Path]:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            raise ValueError("task execution ContextPack requires task id")
        return self.build_and_persist_context_pack(
            query=build_task_context_query(task, docs),
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
            rebuild_if_missing=rebuild_if_missing,
            exclude_task_ids=(task_id,),
            source_task_id=task_id,
            purpose=EXECUTION_CONTEXT_PACK_PURPOSE,
        )

    def persist_context_pack(self, pack: Mapping[str, object]) -> Path:
        return self.packs.write(pack)

    def read_context_pack(self, pack_id: str) -> dict[str, object]:
        return self.packs.read(pack_id)

    def _read_documents(self, *, rebuild_if_missing: bool) -> tuple[SearchDocument, ...]:
        try:
            return self.index.read()
        except FileNotFoundError:
            if not rebuild_if_missing:
                raise
            self.index.rebuild()
            return self.index.read()


def build_task_context_query(
    task: Mapping[str, object],
    docs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    max_chars: int = DEFAULT_CONTEXT_QUERY_CHARS,
) -> str:
    parts: list[str] = [
        str(task.get("id") or ""),
        str(task.get("type") or ""),
        str(task.get("slug") or ""),
        str(task.get("workflow_phase") or ""),
    ]
    meta = task.get("meta", {})
    if isinstance(meta, Mapping):
        parts.append(str(meta.get("requested_slug") or ""))
        owned_paths = meta.get("owned_paths")
        if isinstance(owned_paths, list):
            parts.extend(str(path) for path in owned_paths)
    for label, content in docs:
        if any(key in label.lower() for key in ("brief", "plan", "fix_plan", "repro")):
            parts.extend((label, content))
    normalized = re.sub(r"\s+", " ", "\n".join(parts).replace("`", " ")).strip()
    return normalized if len(normalized) <= max_chars else normalized[:max_chars].rstrip()


def fingerprint_context_pack_payload(payload: Mapping[str, object]) -> str:
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _context_item_from_result(
    result: RetrievalResult,
    *,
    max_excerpt_chars: int,
) -> dict[str, object]:
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
    "DEFAULT_CONTEXT_PACK_EXCERPT_CHARS",
    "DEFAULT_CONTEXT_PACK_LIMIT",
    "DEFAULT_CONTEXT_QUERY_CHARS",
    "EXECUTION_CONTEXT_PACK_PURPOSE",
    "SearchService",
    "build_task_context_query",
    "fingerprint_context_pack_payload",
]
