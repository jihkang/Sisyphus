from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
from typing import Any, Callable

from .file_lock import file_lock


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: object) -> None:
    with file_lock(path):
        _write_json_file_unlocked(path, payload)


def locked_json_update(
    path: Path,
    update: Callable[[Any], object],
    *,
    default_factory: Callable[[], Any] | None = None,
) -> object:
    with file_lock(path):
        if path.exists():
            current = read_json_file(path)
        elif default_factory is not None:
            current = default_factory()
        else:
            raise FileNotFoundError(path)
        payload = update(current)
        _write_json_file_unlocked(path, payload)
        return payload


def _write_json_file_unlocked(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_parent_directory(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _fsync_parent_directory(path: Path) -> None:
    if os.name == "nt":  # pragma: no cover - directory fsync is POSIX-specific.
        return
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


__all__ = [
    "locked_json_update",
    "read_json_file",
    "write_json_file",
]
