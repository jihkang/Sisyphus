from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import PurePosixPath

from .secure_files import SecureWorkspaceFiles, WorkspacePathFingerprint


PROTECTED_MUTATION_PARTS = frozenset({".git", ".planning"})


@dataclass(frozen=True, slots=True)
class WorkspaceTreeSnapshot:
    entries: tuple[tuple[str, WorkspacePathFingerprint], ...]
    tree_hash: str

    def fingerprints(self) -> dict[str, WorkspacePathFingerprint]:
        return dict(self.entries)


@dataclass(frozen=True, slots=True)
class WorkspaceTreeMutation:
    before_hash: str
    after_hash: str
    changed_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    non_regular_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]


class TreeHashMutationGuard:
    def __init__(self, files: SecureWorkspaceFiles) -> None:
        self._files = files

    def capture(self) -> WorkspaceTreeSnapshot:
        entries = tuple(sorted(self._files.snapshot_tree().items()))
        return WorkspaceTreeSnapshot(entries=entries, tree_hash=_tree_hash(entries))

    def inspect(
        self,
        before: WorkspaceTreeSnapshot,
        *,
        declared_paths: frozenset[str],
    ) -> WorkspaceTreeMutation:
        after = self.capture()
        before_entries = before.fingerprints()
        after_entries = after.fingerprints()
        changed = tuple(
            sorted(
                path
                for path in before_entries.keys() | after_entries.keys()
                if before_entries.get(path) != after_entries.get(path)
            )
        )
        unexpected = tuple(path for path in changed if path not in declared_paths)
        non_regular = tuple(
            path
            for path in changed
            if any(
                fingerprint is not None and fingerprint.kind != "regular"
                for fingerprint in (before_entries.get(path), after_entries.get(path))
            )
        )
        protected = tuple(path for path in changed if _is_protected(path))
        return WorkspaceTreeMutation(
            before_hash=before.tree_hash,
            after_hash=after.tree_hash,
            changed_paths=changed,
            unexpected_paths=unexpected,
            non_regular_paths=non_regular,
            protected_paths=protected,
        )


def _tree_hash(entries: tuple[tuple[str, WorkspacePathFingerprint], ...]) -> str:
    digest = hashlib.sha256()
    for path, fingerprint in entries:
        for value in (
            path,
            fingerprint.kind,
            str(fingerprint.mode),
            str(fingerprint.size),
            fingerprint.digest,
        ):
            encoded = value.encode("utf-8", errors="surrogateescape")
            digest.update(len(encoded).to_bytes(8, byteorder="big"))
            digest.update(encoded)
    return "sha256:" + digest.hexdigest()


def _is_protected(path: str) -> bool:
    return any(part in PROTECTED_MUTATION_PARTS for part in PurePosixPath(path).parts)


__all__ = [
    "TreeHashMutationGuard",
    "WorkspaceTreeMutation",
    "WorkspaceTreeSnapshot",
]
