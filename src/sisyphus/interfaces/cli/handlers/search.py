from __future__ import annotations

from pathlib import Path
import json
import sys

from ....application.codecs.search import (
    encode_retrieval_result,
    encode_search_index_rebuild_result,
)
from ....application.search.models import SearchIndexError
from ....composition.search import (
    build_and_persist_context_pack,
    rebuild_search_index,
    search_documents,
)
from ....config import SisyphusConfig


def handle_index_rebuild(*, repo_root: Path, config: SisyphusConfig, as_json: bool) -> int:
    result = rebuild_search_index(repo_root, config)
    payload = encode_search_index_rebuild_result(result)
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"index_path: {result.index_path}")
    print(f"documents: {result.document_count}")
    print(f"changed: {'yes' if result.changed else 'no'}")
    return 0


def handle_search(*, repo_root: Path, query: str, limit: int, as_json: bool) -> int:
    try:
        results = search_documents(repo_root, query=query, limit=limit)
    except FileNotFoundError as exc:
        print(f"error: {exc}; run `sisyphus index rebuild` first", file=sys.stderr)
        return 1
    except SearchIndexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "query": query,
        "result_count": len(results),
        "results": [encode_retrieval_result(result) for result in results],
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    if not results:
        print("no results")
        return 0
    for result in results:
        document = result.document
        print(f"{result.rank}. score={result.score} source={document.source_ref}")
        print(f"   title: {document.title}")
        if document.freshness_status:
            print(f"   freshness: {document.freshness_status}")
        print(f"   excerpt: {result.excerpt}")
    return 0


def handle_context_build(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    query: str,
    limit: int,
    max_excerpt_chars: int,
    as_json: bool,
) -> int:
    try:
        pack, path = build_and_persist_context_pack(
            repo_root,
            config,
            query=query,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
            rebuild_if_missing=True,
        )
    except SearchIndexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    payload = {
        "pack_path": str(path),
        "context_pack": pack,
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"context_pack: {pack['pack_id']}")
    print(f"pack_path: {path}")
    print(f"results: {pack['result_count']}")
    print(f"fingerprint: {pack['fingerprint']}")
    return 0


__all__ = [
    "handle_context_build",
    "handle_index_rebuild",
    "handle_search",
]
