from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import os

if os.name == "nt":  # pragma: no cover - exercised on Windows only.
    import msvcrt
else:  # pragma: no cover - import branch is platform-specific.
    import fcntl


@contextmanager
def file_lock(target_path: Path) -> Iterator[None]:
    lock_path = target_path.with_name(f".{target_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":  # pragma: no cover - exercised on Windows only.
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = [
    "file_lock",
]
