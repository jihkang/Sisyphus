from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..application.search.models import SearchDocument, SearchIndexRebuildResult
from ..application.search.retrieval import RetrievalResult
from ..application.use_cases.search import (
    DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    DEFAULT_CONTEXT_PACK_LIMIT,
    SearchService,
)
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.search import RepositoryContextPackStore, RepositorySearchIndex


def build_search_service(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    index_path: str | Path | None = None,
) -> SearchService:
    return SearchService(
        index=RepositorySearchIndex(
            repo_root,
            config,
            index_path=index_path,
        ),
        packs=RepositoryContextPackStore(repo_root),
        clock=SystemClock(),
    )


def rebuild_search_index(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    index_path: str | Path | None = None,
) -> SearchIndexRebuildResult:
    return build_search_service(repo_root, config, index_path=index_path).rebuild_index()


def read_search_index(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    index_path: str | Path | None = None,
) -> tuple[SearchDocument, ...]:
    return build_search_service(repo_root, config, index_path=index_path).read_index()


def search_index_status(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    index_path: str | Path | None = None,
) -> dict[str, object]:
    return build_search_service(repo_root, config, index_path=index_path).index_status()


def search_documents(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    query: str,
    limit: int,
    rebuild_if_missing: bool = False,
) -> tuple[RetrievalResult, ...]:
    return build_search_service(repo_root, config).search(
        query,
        limit=limit,
        rebuild_if_missing=rebuild_if_missing,
    )


def build_context_pack(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    query: str,
    limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
    max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    rebuild_if_missing: bool = True,
    exclude_task_ids: list[str] | tuple[str, ...] | None = None,
    source_task_id: str | None = None,
    purpose: str | None = None,
) -> dict[str, object]:
    return build_search_service(repo_root, config).build_context_pack(
        query=query,
        limit=limit,
        max_excerpt_chars=max_excerpt_chars,
        rebuild_if_missing=rebuild_if_missing,
        exclude_task_ids=exclude_task_ids,
        source_task_id=source_task_id,
        purpose=purpose,
    )


def build_and_persist_context_pack(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    query: str,
    limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
    max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    rebuild_if_missing: bool = True,
    exclude_task_ids: list[str] | tuple[str, ...] | None = None,
    source_task_id: str | None = None,
    purpose: str | None = None,
) -> tuple[dict[str, object], Path]:
    return build_search_service(repo_root, config).build_and_persist_context_pack(
        query=query,
        limit=limit,
        max_excerpt_chars=max_excerpt_chars,
        rebuild_if_missing=rebuild_if_missing,
        exclude_task_ids=exclude_task_ids,
        source_task_id=source_task_id,
        purpose=purpose,
    )


def build_task_execution_context_pack(
    repo_root: Path,
    config: SisyphusConfig | None = None,
    *,
    task: Mapping[str, object],
    docs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    limit: int = DEFAULT_CONTEXT_PACK_LIMIT,
    max_excerpt_chars: int = DEFAULT_CONTEXT_PACK_EXCERPT_CHARS,
    rebuild_if_missing: bool = True,
) -> tuple[dict[str, object], Path]:
    return build_search_service(repo_root, config).build_task_execution_context_pack(
        task=task,
        docs=docs,
        limit=limit,
        max_excerpt_chars=max_excerpt_chars,
        rebuild_if_missing=rebuild_if_missing,
    )


def persist_context_pack(repo_root: Path, pack: Mapping[str, object]) -> Path:
    return RepositoryContextPackStore(repo_root).write(pack)


def read_context_pack(repo_root: Path, pack_id: str) -> dict[str, object]:
    return RepositoryContextPackStore(repo_root).read(pack_id)


__all__ = [
    "build_and_persist_context_pack",
    "build_context_pack",
    "build_search_service",
    "build_task_execution_context_pack",
    "persist_context_pack",
    "read_context_pack",
    "read_search_index",
    "rebuild_search_index",
    "search_documents",
    "search_index_status",
]
