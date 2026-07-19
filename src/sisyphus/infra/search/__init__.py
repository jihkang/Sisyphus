from __future__ import annotations

from .documents import project_repo_search_documents, project_task_search_documents
from .adapters import (
    DEFAULT_CONTEXT_PACK_DIR,
    RepositoryContextPackStore,
    RepositorySearchIndex,
)
from .index import (
    DEFAULT_SEARCH_INDEX_PATH,
    SearchIndexError,
    SearchIndexRebuildResult,
    read_search_index,
    rebuild_search_index,
    resolve_search_index_path,
    search_index_status,
)

__all__ = [
    "DEFAULT_SEARCH_INDEX_PATH",
    "DEFAULT_CONTEXT_PACK_DIR",
    "RepositoryContextPackStore",
    "RepositorySearchIndex",
    "SearchIndexError",
    "SearchIndexRebuildResult",
    "project_repo_search_documents",
    "project_task_search_documents",
    "read_search_index",
    "rebuild_search_index",
    "resolve_search_index_path",
    "search_index_status",
]
