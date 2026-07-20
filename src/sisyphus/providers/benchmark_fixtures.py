from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import json
import re

from ..infra.workspace import PROTECTED_PATH_PARTS
from .benchmark_models import (
    DEFAULT_LOCAL_AGENT_BENCHMARK_FIXTURE_FILE,
    LOCAL_AGENT_BENCHMARK_FIXTURE_SCHEMA_VERSION,
    LOCAL_AGENT_BENCHMARK_KINDS,
    LocalAgentBenchmarkFixture,
    LocalAgentBenchmarkFixtureError,
)


_FIXTURE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MAX_FIXTURE_COUNT = 100
_MAX_FIXTURE_FILES = 100
_MAX_FIXTURE_CONTENT_CHARS = 1_000_000
_MAX_PROMPT_CHARS = 20_000
_MAX_TEST_COMMANDS = 16


def default_local_agent_benchmark_fixture_file(repo_root: Path) -> Path:
    return repo_root / DEFAULT_LOCAL_AGENT_BENCHMARK_FIXTURE_FILE


def load_local_agent_benchmark_fixtures(
    fixture_file: Path,
) -> tuple[LocalAgentBenchmarkFixture, ...]:
    try:
        payload = json.loads(fixture_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalAgentBenchmarkFixtureError(
            f"local-agent benchmark fixture file does not exist: {fixture_file}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LocalAgentBenchmarkFixtureError(
            f"invalid local-agent benchmark JSON in {fixture_file}: {exc.msg}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise LocalAgentBenchmarkFixtureError(
            f"cannot read local-agent benchmark fixture file {fixture_file}: {exc}"
        ) from exc

    if not isinstance(payload, Mapping):
        raise LocalAgentBenchmarkFixtureError(
            "local-agent benchmark fixture root must be a JSON object"
        )
    if payload.get("schema_version") != LOCAL_AGENT_BENCHMARK_FIXTURE_SCHEMA_VERSION:
        raise LocalAgentBenchmarkFixtureError(
            f"unsupported local-agent benchmark fixture schema in {fixture_file}"
        )
    items = payload.get("fixtures")
    if not isinstance(items, list) or not items:
        raise LocalAgentBenchmarkFixtureError("fixtures must be a non-empty list")
    if len(items) > _MAX_FIXTURE_COUNT:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture count exceeds {_MAX_FIXTURE_COUNT}"
        )

    fixtures = tuple(_parse_fixture(item, fixture_file) for item in items)
    identifiers = [fixture.fixture_id for fixture in fixtures]
    duplicates = sorted(
        fixture_id for fixture_id in set(identifiers) if identifiers.count(fixture_id) > 1
    )
    if duplicates:
        raise LocalAgentBenchmarkFixtureError(
            f"duplicate local-agent benchmark fixture IDs: {duplicates}"
        )
    return fixtures


def validate_local_agent_benchmark_fixture(
    fixture: LocalAgentBenchmarkFixture,
) -> LocalAgentBenchmarkFixture:
    if not isinstance(fixture, LocalAgentBenchmarkFixture):
        raise LocalAgentBenchmarkFixtureError(
            "benchmark runner requires LocalAgentBenchmarkFixture entries"
        )
    try:
        files = dict(fixture.files)
    except (TypeError, ValueError) as exc:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture.fixture_id!r} has invalid file entries"
        ) from exc
    if len(files) != len(fixture.files):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture.fixture_id!r} contains duplicate file paths"
        )
    return _parse_fixture(
        {
            "id": fixture.fixture_id,
            "title": fixture.title,
            "kind": fixture.kind,
            "prompt": fixture.prompt,
            "files": files,
            "owned_paths": list(fixture.owned_paths),
            "test_commands": list(fixture.test_commands),
            "expected_changed_paths": list(fixture.expected_changed_paths),
            "min_compactions": fixture.min_compactions,
        },
        Path("<benchmark-runner>"),
    )


def _parse_fixture(item: object, source: Path) -> LocalAgentBenchmarkFixture:
    if not isinstance(item, Mapping):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture entries must be JSON objects in {source}"
        )
    fixture_id = _required_text(item, "id")
    if not _FIXTURE_ID_PATTERN.fullmatch(fixture_id):
        raise LocalAgentBenchmarkFixtureError(
            f"invalid local-agent benchmark fixture ID: {fixture_id!r}"
        )
    title = _required_text(item, "title")
    kind = _required_text(item, "kind")
    if kind not in LOCAL_AGENT_BENCHMARK_KINDS:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} has unknown kind {kind!r}"
        )
    prompt = _required_text(item, "prompt")
    if len(prompt) > _MAX_PROMPT_CHARS:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} prompt exceeds {_MAX_PROMPT_CHARS} characters"
        )

    files_payload = item.get("files")
    if not isinstance(files_payload, Mapping) or not files_payload:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} files must be a non-empty object"
        )
    if len(files_payload) > _MAX_FIXTURE_FILES:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} file count exceeds {_MAX_FIXTURE_FILES}"
        )
    files: list[tuple[str, str]] = []
    total_chars = 0
    for raw_path, content in files_payload.items():
        path = _normalize_fixture_path(raw_path, fixture_id=fixture_id)
        if not isinstance(content, str):
            raise LocalAgentBenchmarkFixtureError(
                f"fixture {fixture_id} file {path} content must be a string"
            )
        total_chars += len(content)
        files.append((path, content))
    if total_chars > _MAX_FIXTURE_CONTENT_CHARS:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} content exceeds {_MAX_FIXTURE_CONTENT_CHARS} characters"
        )
    _validate_file_collisions(fixture_id, tuple(path for path, _content in files))

    owned_paths = _path_list(item, "owned_paths", fixture_id=fixture_id, non_empty=True)
    test_commands = _text_list(item, "test_commands", fixture_id=fixture_id)
    if not test_commands or len(test_commands) > _MAX_TEST_COMMANDS:
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} test_commands must contain 1-{_MAX_TEST_COMMANDS} entries"
        )
    expected_paths = _path_list(
        item,
        "expected_changed_paths",
        fixture_id=fixture_id,
        non_empty=kind == "coding",
    )
    if kind == "safety" and expected_paths:
        raise LocalAgentBenchmarkFixtureError(
            f"safety fixture {fixture_id} cannot expect changed paths"
        )
    for path in expected_paths:
        if not any(_path_is_owned(path, owned_path) for owned_path in owned_paths):
            raise LocalAgentBenchmarkFixtureError(
                f"fixture {fixture_id} expected path is outside owned_paths: {path}"
            )

    min_compactions = item.get("min_compactions", 0)
    if (
        isinstance(min_compactions, bool)
        or not isinstance(min_compactions, int)
        or min_compactions < 0
    ):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} min_compactions must be a non-negative integer"
        )
    return LocalAgentBenchmarkFixture(
        fixture_id=fixture_id,
        title=title,
        kind=kind,
        prompt=prompt,
        files=tuple(sorted(files)),
        owned_paths=tuple(sorted(owned_paths)),
        test_commands=test_commands,
        expected_changed_paths=tuple(sorted(expected_paths)),
        min_compactions=min_compactions,
    )


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LocalAgentBenchmarkFixtureError(f"fixture {key} must be a non-empty string")
    return value.strip()


def _text_list(
    payload: Mapping[str, object],
    key: str,
    *,
    fixture_id: str,
) -> tuple[str, ...]:
    values = payload.get(key)
    if not isinstance(values, list):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} {key} must be a list"
        )
    rendered: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise LocalAgentBenchmarkFixtureError(
                f"fixture {fixture_id} {key} entries must be non-empty strings"
            )
        rendered.append(value.strip())
    return tuple(rendered)


def _path_list(
    payload: Mapping[str, object],
    key: str,
    *,
    fixture_id: str,
    non_empty: bool,
) -> tuple[str, ...]:
    values = payload.get(key)
    if not isinstance(values, list) or (non_empty and not values):
        qualifier = "non-empty " if non_empty else ""
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} {key} must be a {qualifier}list"
        )
    paths = tuple(
        _normalize_fixture_path(value, fixture_id=fixture_id) for value in values
    )
    if len(paths) != len({path.casefold() for path in paths}):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} {key} contains duplicate paths"
        )
    return paths


def _normalize_fixture_path(value: object, *, fixture_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} paths must be non-empty strings"
        )
    raw = value.strip()
    if "\\" in raw or "\x00" in raw or raw.startswith("/"):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} path must be relative POSIX syntax: {raw}"
        )
    raw_parts = raw.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in raw_parts):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} path contains unsafe traversal: {raw}"
        )
    path = PurePosixPath(raw)
    if any(part in PROTECTED_PATH_PARTS for part in path.parts):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} path enters a protected location: {raw}"
        )
    return path.as_posix()


def _validate_file_collisions(fixture_id: str, paths: tuple[str, ...]) -> None:
    casefolded_paths = [path.casefold() for path in paths]
    if len(casefolded_paths) != len(set(casefolded_paths)):
        raise LocalAgentBenchmarkFixtureError(
            f"fixture {fixture_id} file paths collide by case"
        )
    path_set = set(casefolded_paths)
    for path in paths:
        parents = PurePosixPath(path).parents
        if any(
            parent.as_posix().casefold() in path_set
            for parent in parents
            if parent.as_posix() != "."
        ):
            raise LocalAgentBenchmarkFixtureError(
                f"fixture {fixture_id} file paths collide at {path}"
            )


def _path_is_owned(path: str, owned_path: str) -> bool:
    return path == owned_path or path.startswith(owned_path.rstrip("/") + "/")


__all__ = [
    "default_local_agent_benchmark_fixture_file",
    "load_local_agent_benchmark_fixtures",
    "validate_local_agent_benchmark_fixture",
]
