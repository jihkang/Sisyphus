from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import stat

from ...application.evolution_runs import (
    validate_evolution_artifact_name,
    validate_evolution_run_id,
)
from ...shared.paths import PathBoundaryError


DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT = 8 * 1024 * 1024
_RUNS_ROOT_PARTS = (".planning", "evolution", "runs")
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
_CREATE_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)


class RepositoryEvolutionRunStore:
    def __init__(
        self,
        repo_root: Path,
        *,
        read_limit: int = DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT,
    ) -> None:
        if read_limit < 1:
            raise ValueError("evolution artifact read limit must be positive")
        if not _secure_directory_operations_supported():
            raise RuntimeError(
                "evolution run storage requires descriptor-relative no-follow operations"
            )
        self._repo_root = repo_root.resolve()
        self._runs_root = self._repo_root.joinpath(*_RUNS_ROOT_PARTS)
        self._read_limit = read_limit
        self._root_fd = os.open(self._repo_root, _DIRECTORY_FLAGS)

    def close(self) -> None:
        root_fd = getattr(self, "_root_fd", -1)
        if root_fd >= 0:
            os.close(root_fd)
            self._root_fd = -1

    def __enter__(self) -> RepositoryEvolutionRunStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except OSError:
            pass

    def create_run(self, run_id: str) -> Path:
        normalized_run_id = validate_evolution_run_id(run_id)
        with self._open_runs_dir(create=True) as runs_fd:
            _mkdir_at(runs_fd, normalized_run_id, relative=normalized_run_id)
            os.fsync(runs_fd)
        return self._runs_root / normalized_run_id

    def artifact_dir(self, run_id: str) -> Path:
        return self._runs_root / validate_evolution_run_id(run_id)

    def run_exists(self, run_id: str) -> bool:
        normalized_run_id = validate_evolution_run_id(run_id)
        try:
            with self._open_runs_dir(create=False) as runs_fd:
                metadata = os.stat(
                    normalized_run_id,
                    dir_fd=runs_fd,
                    follow_symlinks=False,
                )
        except FileNotFoundError:
            return False
        return stat.S_ISDIR(metadata.st_mode)

    def artifact_exists(self, run_id: str, name: str) -> bool:
        normalized_name = validate_evolution_artifact_name(name)
        try:
            with self._open_run_dir(run_id) as run_fd:
                metadata = os.stat(
                    normalized_name,
                    dir_fd=run_fd,
                    follow_symlinks=False,
                )
        except FileNotFoundError:
            return False
        return stat.S_ISREG(metadata.st_mode)

    def append_json(
        self,
        run_id: str,
        name: str,
        payload: Mapping[str, object],
    ) -> Path:
        rendered = json.dumps(dict(payload), indent=2) + "\n"
        return self.append_text(run_id, name, rendered)

    def append_text(self, run_id: str, name: str, content: str) -> Path:
        normalized_run_id = validate_evolution_run_id(run_id)
        normalized_name = validate_evolution_artifact_name(name)
        payload = content.encode("utf-8")
        with self._open_run_dir(normalized_run_id) as run_fd:
            _reject_symlink_at(run_fd, normalized_name, relative=normalized_name)
            descriptor = os.open(
                normalized_name,
                _CREATE_FLAGS,
                0o644,
                dir_fd=run_fd,
            )
            try:
                _write_all(descriptor, payload)
                os.fsync(descriptor)
            except BaseException:
                try:
                    os.unlink(normalized_name, dir_fd=run_fd)
                except FileNotFoundError:
                    pass
                raise
            finally:
                os.close(descriptor)
            os.fsync(run_fd)
        return self._runs_root / normalized_run_id / normalized_name

    def read_json(self, run_id: str, name: str) -> Mapping[str, object] | None:
        text = self.read_text(run_id, name)
        if text is None:
            return None
        payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise ValueError(f"evolution run artifact must be an object: {name}")
        return {str(key): value for key, value in payload.items()}

    def read_text(self, run_id: str, name: str) -> str | None:
        normalized_name = validate_evolution_artifact_name(name)
        try:
            with self._open_run_dir(run_id) as run_fd:
                try:
                    descriptor = os.open(normalized_name, _READ_FLAGS, dir_fd=run_fd)
                except FileNotFoundError:
                    return None
                except OSError as exc:
                    _raise_if_unsafe_path(exc, normalized_name)
                    raise
                try:
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode):
                        raise PathBoundaryError(
                            f"evolution artifact is not a regular file: {normalized_name}"
                        )
                    if metadata.st_size > self._read_limit:
                        raise ValueError(
                            f"evolution run artifact exceeds read limit: {name}"
                        )
                    content = _read_bounded(
                        descriptor,
                        max_bytes=self._read_limit,
                        name=normalized_name,
                    )
                finally:
                    os.close(descriptor)
        except FileNotFoundError:
            return None
        return content.decode("utf-8")

    @contextmanager
    def _open_runs_dir(self, *, create: bool) -> Iterator[int]:
        if self._root_fd < 0:
            raise RuntimeError("evolution run store is closed")
        descriptors = [os.dup(self._root_fd)]
        try:
            for index, part in enumerate(_RUNS_ROOT_PARTS):
                parent_fd = descriptors[-1]
                try:
                    child_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=parent_fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    relative = "/".join(_RUNS_ROOT_PARTS[: index + 1])
                    _mkdir_at(parent_fd, part, relative=relative)
                    os.fsync(parent_fd)
                    child_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=parent_fd)
                except OSError as exc:
                    _raise_if_unsafe_path(
                        exc,
                        "/".join(_RUNS_ROOT_PARTS[: index + 1]),
                    )
                    raise
                descriptors.append(child_fd)
            yield descriptors[-1]
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @contextmanager
    def _open_run_dir(self, run_id: str) -> Iterator[int]:
        normalized_run_id = validate_evolution_run_id(run_id)
        with self._open_runs_dir(create=False) as runs_fd:
            try:
                run_fd = os.open(
                    normalized_run_id,
                    _DIRECTORY_FLAGS,
                    dir_fd=runs_fd,
                )
            except OSError as exc:
                _raise_if_unsafe_path(exc, normalized_run_id)
                raise
            try:
                yield run_fd
            finally:
                os.close(run_fd)


def _secure_directory_operations_supported() -> bool:
    return bool(getattr(os, "O_NOFOLLOW", 0)) and all(
        function in os.supports_dir_fd
        for function in (os.mkdir, os.open, os.stat, os.unlink)
    ) and os.stat in os.supports_follow_symlinks


def _mkdir_at(parent_fd: int, name: str, *, relative: str) -> None:
    try:
        os.mkdir(name, 0o755, dir_fd=parent_fd)
    except FileExistsError:
        try:
            metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            _raise_if_unsafe_path(exc, relative)
            raise
        if stat.S_ISLNK(metadata.st_mode):
            raise PathBoundaryError(f"evolution storage path is a symlink: {relative}")
        raise


def _reject_symlink_at(parent_fd: int, name: str, *, relative: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise PathBoundaryError(f"evolution artifact is a symlink: {relative}")


def _raise_if_unsafe_path(exc: OSError, relative: str) -> None:
    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
        raise PathBoundaryError(
            f"evolution storage path crosses a symlink: {relative}"
        ) from exc


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("failed to write evolution artifact")
        offset += written


def _read_bounded(descriptor: int, *, max_bytes: int, name: str) -> bytes:
    chunks: list[bytes] = []
    remaining = max_bytes + 1
    while remaining > 0:
        chunk = os.read(descriptor, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    content = b"".join(chunks)
    if len(content) > max_bytes:
        raise ValueError(f"evolution run artifact exceeds read limit: {name}")
    return content


__all__ = ["DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT", "RepositoryEvolutionRunStore"]
