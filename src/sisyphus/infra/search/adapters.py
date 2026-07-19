from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from pathlib import Path
import re
from typing import Any

from ...application.search.models import SearchDocument, SearchIndexRebuildResult
from ...application.use_cases.search import CONTEXT_PACK_SCHEMA_VERSION
from ...shared.paths import contained_path
from ..config.loader import SisyphusConfig, load_config
from ..persistence.atomic_text import write_text_file
from ..persistence.json_store import read_json_file
from .index import read_search_index, rebuild_search_index, search_index_status


DEFAULT_CONTEXT_PACK_DIR = Path(".planning") / "context-packs"
CONTEXT_PACK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class RepositorySearchIndex:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig | None = None,
        *,
        index_path: str | Path | None = None,
        config_loader: Callable[[Path], SisyphusConfig] = load_config,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._index_path = index_path
        self._config_loader = config_loader

    def rebuild(self) -> SearchIndexRebuildResult:
        return rebuild_search_index(
            self._repo_root,
            self._config or self._config_loader(self._repo_root),
            index_path=self._index_path,
        )

    def read(self) -> tuple[SearchDocument, ...]:
        return read_search_index(self._repo_root, index_path=self._index_path)

    def status(self) -> dict[str, object]:
        return search_index_status(self._repo_root, index_path=self._index_path)


class RepositoryContextPackStore:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def write(self, pack: Mapping[str, object]) -> Path:
        pack_id = _validated_pack_id(
            pack.get("pack_id"),
            missing_message="context pack requires pack_id before persistence",
        )
        path = self._path(pack_id)
        rendered = json.dumps(_json_safe(dict(pack)), indent=2, sort_keys=True) + "\n"
        write_text_file(path, rendered)
        return path

    def read(self, pack_id: str) -> dict[str, object]:
        normalized_pack_id = _validated_pack_id(
            pack_id,
            missing_message="context pack id must be non-empty",
        )
        path = self._path(normalized_pack_id)
        if not path.exists():
            raise FileNotFoundError(f"context pack not found: {normalized_pack_id}")
        raw = read_json_file(path)
        if not isinstance(raw, dict):
            raise ValueError(f"context pack must be an object: {path}")
        schema_version = str(raw.get("schema_version") or "")
        if schema_version != CONTEXT_PACK_SCHEMA_VERSION:
            raise ValueError(
                "context pack schema_version must be "
                f"{CONTEXT_PACK_SCHEMA_VERSION!r}, got {schema_version!r}"
            )
        return {str(key): value for key, value in raw.items()}

    def _path(self, pack_id: str) -> Path:
        return contained_path(
            self._repo_root,
            DEFAULT_CONTEXT_PACK_DIR / f"{pack_id}.json",
            require_relative=True,
        )


def _validated_pack_id(value: object, *, missing_message: str) -> str:
    pack_id = str(value or "").strip()
    if not pack_id:
        raise ValueError(missing_message)
    if CONTEXT_PACK_ID_PATTERN.fullmatch(pack_id) is None:
        raise ValueError(f"invalid context pack id: {pack_id!r}")
    return pack_id


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "CONTEXT_PACK_ID_PATTERN",
    "DEFAULT_CONTEXT_PACK_DIR",
    "RepositoryContextPackStore",
    "RepositorySearchIndex",
]
