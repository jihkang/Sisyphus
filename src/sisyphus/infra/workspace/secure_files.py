from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import errno
import hashlib
import os
import secrets
import stat

from .errors import WorkspaceFileSafetyError


_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
_WRITE_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)


@dataclass(frozen=True, slots=True)
class WorkspacePathFingerprint:
    kind: str
    mode: int
    size: int
    digest: str


class SecureWorkspaceFiles:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._dir_fd_supported = all(
            function in os.supports_dir_fd
            for function in (os.open, os.mkdir, os.stat, os.rename, os.unlink)
        ) and bool(getattr(os, "O_NOFOLLOW", 0))

    def read_text(self, relative: PurePosixPath, *, max_bytes: int) -> str:
        if self._dir_fd_supported:
            data = self._read_bytes_at(relative, max_bytes=max_bytes)
        else:
            data = self._read_bytes_fallback(relative, max_bytes=max_bytes)
        return data.decode("utf-8")

    def write_text_atomic(self, relative: PurePosixPath, content: str) -> bool:
        payload = content.encode("utf-8")
        if self._dir_fd_supported:
            return self._write_bytes_at(relative, payload)
        return self._write_bytes_fallback(relative, payload)

    def reject_existing_symlinks(self, relative: PurePosixPath) -> None:
        current = self.root
        for part in relative.parts:
            if part == ".":
                continue
            current = current / part
            try:
                metadata = current.lstat()
            except FileNotFoundError:
                return
            if stat.S_ISLNK(metadata.st_mode):
                raise WorkspaceFileSafetyError(
                    f"workspace path contains a symlink: {relative.as_posix()}"
                )

    def snapshot_tree(
        self,
        *,
        excluded_names: frozenset[str] = frozenset({".git"}),
    ) -> dict[str, WorkspacePathFingerprint]:
        if self._dir_fd_supported and os.scandir in os.supports_fd:
            root_fd = os.open(self.root, _DIRECTORY_FLAGS)
            try:
                result: dict[str, WorkspacePathFingerprint] = {}
                self._snapshot_tree_at(
                    root_fd,
                    prefix=PurePosixPath("."),
                    excluded_names=excluded_names,
                    result=result,
                )
                return result
            finally:
                os.close(root_fd)
        return self._snapshot_tree_fallback(excluded_names=excluded_names)

    def _read_bytes_at(self, relative: PurePosixPath, *, max_bytes: int) -> bytes:
        with self._parent_fd(relative, create=False) as (parent_fd, leaf):
            return self._read_leaf_at(
                parent_fd,
                leaf,
                relative=relative,
                max_bytes=max_bytes,
            )

    def _write_bytes_at(self, relative: PurePosixPath, payload: bytes) -> bool:
        with self._parent_fd(relative, create=True) as (parent_fd, leaf):
            existing_mode: int | None = None
            try:
                metadata = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                metadata = None
            if metadata is not None:
                if not stat.S_ISREG(metadata.st_mode):
                    raise WorkspaceFileSafetyError(
                        f"workspace write target is not a regular file: {relative.as_posix()}"
                    )
                existing_mode = stat.S_IMODE(metadata.st_mode)
                if metadata.st_size == len(payload) and self._read_leaf_at(
                    parent_fd,
                    leaf,
                    relative=relative,
                    max_bytes=max(len(payload), 1),
                ) == payload:
                    return False

            temporary_name = f".{leaf}.{secrets.token_hex(8)}.tmp"
            temporary_fd: int | None = None
            try:
                temporary_fd = os.open(
                    temporary_name,
                    _WRITE_FLAGS,
                    0o600,
                    dir_fd=parent_fd,
                )
                _write_all(temporary_fd, payload)
                if existing_mode is not None:
                    os.fchmod(temporary_fd, existing_mode)
                os.fsync(temporary_fd)
                os.close(temporary_fd)
                temporary_fd = None
                os.rename(
                    temporary_name,
                    leaf,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                os.fsync(parent_fd)
            finally:
                if temporary_fd is not None:
                    os.close(temporary_fd)
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
            return True

    def _read_leaf_at(
        self,
        parent_fd: int,
        leaf: str,
        *,
        relative: PurePosixPath,
        max_bytes: int,
    ) -> bytes:
        try:
            file_fd = os.open(leaf, _FILE_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            self._raise_for_unsafe_open(exc, relative)
            raise
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceFileSafetyError(
                    f"workspace path is not a regular file: {relative.as_posix()}"
                )
            if metadata.st_size > max_bytes:
                raise WorkspaceFileSafetyError(
                    f"file exceeds workspace read limit of {max_bytes} bytes: {relative.as_posix()}"
                )
            return _read_bounded(file_fd, max_bytes=max_bytes, relative=relative)
        finally:
            os.close(file_fd)

    def _snapshot_tree_at(
        self,
        directory_fd: int,
        *,
        prefix: PurePosixPath,
        excluded_names: frozenset[str],
        result: dict[str, WorkspacePathFingerprint],
    ) -> None:
        try:
            with os.scandir(directory_fd) as entries:
                names = sorted(entry.name for entry in entries)
        except OSError as exc:
            raise WorkspaceFileSafetyError("workspace tree changed during snapshot") from exc

        for name in names:
            if name in excluded_names:
                continue
            relative = PurePosixPath(name) if prefix == PurePosixPath(".") else prefix / name
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise WorkspaceFileSafetyError(
                    f"workspace tree changed during snapshot: {relative.as_posix()}"
                ) from exc
            if stat.S_ISDIR(metadata.st_mode):
                try:
                    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)
                except OSError as exc:
                    self._raise_for_unsafe_open(exc, relative)
                    raise WorkspaceFileSafetyError(
                        f"workspace tree changed during snapshot: {relative.as_posix()}"
                    ) from exc
                try:
                    self._snapshot_tree_at(
                        child_fd,
                        prefix=relative,
                        excluded_names=excluded_names,
                        result=result,
                    )
                finally:
                    os.close(child_fd)
                continue
            result[relative.as_posix()] = self._fingerprint_leaf_at(
                directory_fd,
                name,
                relative=relative,
                metadata=metadata,
            )

    def _fingerprint_leaf_at(
        self,
        parent_fd: int,
        leaf: str,
        *,
        relative: PurePosixPath,
        metadata: os.stat_result,
    ) -> WorkspacePathFingerprint:
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(leaf, dir_fd=parent_fd)
            except OSError as exc:
                raise WorkspaceFileSafetyError(
                    f"workspace tree changed during snapshot: {relative.as_posix()}"
                ) from exc
            return WorkspacePathFingerprint(
                kind="symlink",
                mode=mode,
                size=metadata.st_size,
                digest=_digest_bytes(os.fsencode(target)),
            )
        if not stat.S_ISREG(metadata.st_mode):
            return WorkspacePathFingerprint(
                kind="special",
                mode=mode,
                size=metadata.st_size,
                digest="",
            )
        try:
            file_fd = os.open(leaf, _FILE_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            self._raise_for_unsafe_open(exc, relative)
            raise WorkspaceFileSafetyError(
                f"workspace tree changed during snapshot: {relative.as_posix()}"
            ) from exc
        try:
            opened = os.fstat(file_fd)
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev,
                opened.st_ino,
            ) != (metadata.st_dev, metadata.st_ino):
                raise WorkspaceFileSafetyError(
                    f"workspace tree changed during snapshot: {relative.as_posix()}"
                )
            digest = _digest_file(file_fd)
            finished = os.fstat(file_fd)
            if (
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            ) != (
                finished.st_size,
                finished.st_mtime_ns,
                finished.st_ctime_ns,
            ):
                raise WorkspaceFileSafetyError(
                    f"workspace file changed during snapshot: {relative.as_posix()}"
                )
            return WorkspacePathFingerprint(
                kind="regular",
                mode=stat.S_IMODE(opened.st_mode),
                size=opened.st_size,
                digest=digest,
            )
        finally:
            os.close(file_fd)

    @contextmanager
    def _parent_fd(
        self,
        relative: PurePosixPath,
        *,
        create: bool,
    ) -> Iterator[tuple[int, str]]:
        parts = tuple(part for part in relative.parts if part != ".")
        if not parts:
            raise WorkspaceFileSafetyError("workspace path must identify a file")
        current_fd = os.open(self.root, _DIRECTORY_FLAGS)
        try:
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, mode=0o777, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                    try:
                        next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
                    except OSError as exc:
                        self._raise_for_unsafe_open(exc, relative)
                        raise
                except OSError as exc:
                    self._raise_for_unsafe_open(exc, relative)
                    raise
                os.close(current_fd)
                current_fd = next_fd
            yield current_fd, parts[-1]
        finally:
            os.close(current_fd)

    def _snapshot_tree_fallback(
        self,
        *,
        excluded_names: frozenset[str],
    ) -> dict[str, WorkspacePathFingerprint]:
        result: dict[str, WorkspacePathFingerprint] = {}
        stack = [self.root]
        while stack:
            directory = stack.pop()
            try:
                entries = sorted(directory.iterdir(), key=lambda path: path.name)
            except OSError as exc:
                raise WorkspaceFileSafetyError("workspace tree changed during snapshot") from exc
            for path in entries:
                if path.name in excluded_names:
                    continue
                relative = PurePosixPath(path.relative_to(self.root).as_posix())
                try:
                    metadata = path.lstat()
                except OSError as exc:
                    raise WorkspaceFileSafetyError(
                        f"workspace tree changed during snapshot: {relative.as_posix()}"
                    ) from exc
                if stat.S_ISDIR(metadata.st_mode):
                    stack.append(path)
                    continue
                if stat.S_ISLNK(metadata.st_mode):
                    result[relative.as_posix()] = WorkspacePathFingerprint(
                        kind="symlink",
                        mode=stat.S_IMODE(metadata.st_mode),
                        size=metadata.st_size,
                        digest=_digest_bytes(os.fsencode(os.readlink(path))),
                    )
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    result[relative.as_posix()] = WorkspacePathFingerprint(
                        kind="special",
                        mode=stat.S_IMODE(metadata.st_mode),
                        size=metadata.st_size,
                        digest="",
                    )
                    continue
                try:
                    file_fd = os.open(path, _FILE_FLAGS)
                except OSError as exc:
                    self._raise_for_unsafe_open(exc, relative)
                    raise WorkspaceFileSafetyError(
                        f"workspace tree changed during snapshot: {relative.as_posix()}"
                    ) from exc
                try:
                    opened = os.fstat(file_fd)
                    digest = _digest_file(file_fd)
                    finished = os.fstat(file_fd)
                    if (
                        opened.st_size,
                        opened.st_mtime_ns,
                        opened.st_ctime_ns,
                    ) != (
                        finished.st_size,
                        finished.st_mtime_ns,
                        finished.st_ctime_ns,
                    ):
                        raise WorkspaceFileSafetyError(
                            f"workspace file changed during snapshot: {relative.as_posix()}"
                        )
                    result[relative.as_posix()] = WorkspacePathFingerprint(
                        kind="regular",
                        mode=stat.S_IMODE(opened.st_mode),
                        size=opened.st_size,
                        digest=digest,
                    )
                finally:
                    os.close(file_fd)
        return result

    def _read_bytes_fallback(self, relative: PurePosixPath, *, max_bytes: int) -> bytes:
        path = self._fallback_path(relative)
        with path.open("rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceFileSafetyError(
                    f"workspace path is not a regular file: {relative.as_posix()}"
                )
            if metadata.st_size > max_bytes:
                raise WorkspaceFileSafetyError(
                    f"file exceeds workspace read limit of {max_bytes} bytes: {relative.as_posix()}"
                )
            return _read_bounded(handle.fileno(), max_bytes=max_bytes, relative=relative)

    def _write_bytes_fallback(self, relative: PurePosixPath, payload: bytes) -> bool:
        path = self._fallback_path(relative)
        if path.exists():
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceFileSafetyError(
                    f"workspace write target is not a regular file: {relative.as_posix()}"
                )
            if metadata.st_size == len(payload) and self._read_bytes_fallback(
                relative,
                max_bytes=max(len(payload), 1),
            ) == payload:
                return False
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if existing_mode is not None:
                temporary.chmod(existing_mode)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return True

    def _fallback_path(self, relative: PurePosixPath) -> Path:
        candidate = self.root.joinpath(*relative.parts)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceFileSafetyError(
                f"path escapes local agent workspace: {relative.as_posix()}"
            ) from exc
        current = self.root
        for part in relative.parts:
            if part == ".":
                continue
            current = current / part
            if current.is_symlink():
                raise WorkspaceFileSafetyError(
                    f"workspace path contains a symlink: {relative.as_posix()}"
                )
        return candidate

    @staticmethod
    def _raise_for_unsafe_open(exc: OSError, relative: PurePosixPath) -> None:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise WorkspaceFileSafetyError(
                f"workspace path contains a symlink or non-directory: {relative.as_posix()}"
            ) from exc


def _read_bounded(file_fd: int, *, max_bytes: int, relative: PurePosixPath) -> bytes:
    chunks: list[bytes] = []
    remaining = max_bytes + 1
    while remaining > 0:
        chunk = os.read(file_fd, min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > max_bytes:
        raise WorkspaceFileSafetyError(
            f"file exceeds workspace read limit of {max_bytes} bytes: {relative.as_posix()}"
        )
    return data


def _write_all(file_fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(file_fd, payload[offset:])
        if written <= 0:
            raise OSError("workspace write returned no progress")
        offset += written


def _digest_file(file_fd: int) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = os.read(file_fd, 64 * 1024)
        if not chunk:
            return "sha256:" + digest.hexdigest()
        digest.update(chunk)


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


__all__ = ["SecureWorkspaceFiles", "WorkspacePathFingerprint"]
