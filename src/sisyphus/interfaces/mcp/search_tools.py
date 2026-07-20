from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

from ...application.codecs.search import (
    encode_retrieval_result,
    encode_search_index_rebuild_result,
)
from ...application.search.retrieval import retrieve_documents
from ...composition.search import (
    build_and_persist_context_pack,
    read_search_index,
    rebuild_search_index,
)
from ...config import SisyphusConfig


def _search_index_rebuild(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    rebuild_index=rebuild_search_index,
    **_: object,
) -> dict[str, object]:
    result = rebuild_index(repo_root, config)
    return encode_search_index_rebuild_result(result)


def _search(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    rebuild_index=rebuild_search_index,
    read_index=read_search_index,
    retrieve=retrieve_documents,
    **_: object,
) -> dict[str, object]:
    rebuild_if_missing = bool(args.get("rebuild_if_missing", False))
    try:
        documents = read_index(repo_root)
    except FileNotFoundError:
        if not rebuild_if_missing:
            raise
        rebuild_index(repo_root, config)
        documents = read_index(repo_root)
    results = retrieve(
        str(args["query"]),
        documents,
        limit=int(args.get("limit", 10)),
    )
    return {
        "query": str(args["query"]),
        "result_count": len(results),
        "results": [encode_retrieval_result(result) for result in results],
    }


def _context_build(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    build_context_pack=build_and_persist_context_pack,
    **_: object,
) -> dict[str, object]:
    pack, path = build_context_pack(
        repo_root,
        config,
        query=str(args["query"]),
        limit=int(args.get("limit", 5)),
        max_excerpt_chars=int(args.get("max_excerpt_chars", 800)),
        rebuild_if_missing=bool(args.get("rebuild_if_missing", True)),
    )
    return {
        "pack_path": str(path),
        "context_pack": pack,
    }


TOOL_EXECUTORS = MappingProxyType(
    {
        "sisyphus.search_index_rebuild": _search_index_rebuild,
        "sisyphus.search": _search,
        "sisyphus.context_build": _context_build,
    }
)


def call_search_tool(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    tool_name: str,
    args: dict[str, object],
    rebuild_index=rebuild_search_index,
    read_index=read_search_index,
    retrieve=retrieve_documents,
    build_context_pack=build_and_persist_context_pack,
) -> dict[str, object] | None:
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return None
    return executor(
        repo_root=repo_root,
        config=config,
        args=args,
        rebuild_index=rebuild_index,
        read_index=read_index,
        retrieve=retrieve,
        build_context_pack=build_context_pack,
    )


__all__ = ["TOOL_EXECUTORS", "call_search_tool"]
