from __future__ import annotations

from pathlib import Path
import os
import tempfile

from .file_lock import file_lock


def write_text_file(path: Path, content: str) -> None:
    with file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            _fsync_directory(path.parent)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":  # pragma: no cover - directory fsync is POSIX-specific.
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = ["write_text_file"]
