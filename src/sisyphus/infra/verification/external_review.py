from __future__ import annotations

from pathlib import Path, PurePosixPath
import hashlib

from ...application.ports.review import ExternalReviewEvidence, ExternalReviewEvidenceError
from ...gitops import GitOperationError, current_head_sha, list_dirty_paths
from ..workspace import SecureWorkspaceFiles
from ..workspace.errors import WorkspaceFileSafetyError


MAX_EXTERNAL_REVIEW_REPORT_BYTES = 1024 * 1024


class GitExternalReviewEvidenceAdapter:
    def inspect(self, workspace: str, relative_path: str) -> ExternalReviewEvidence:
        root = Path(workspace)
        if not root.is_dir():
            raise ExternalReviewEvidenceError(f"task worktree does not exist: {workspace}")
        try:
            relative = PurePosixPath(relative_path)
            report = SecureWorkspaceFiles(root).read_text(
                relative,
                max_bytes=MAX_EXTERNAL_REVIEW_REPORT_BYTES,
            )
            if not report.strip():
                raise ExternalReviewEvidenceError("external review report must be non-empty")
            payload = report.encode("utf-8")
            changed_paths, deleted_paths = list_dirty_paths(root)
            dirty_paths = tuple(sorted({*changed_paths, *deleted_paths}))
            return ExternalReviewEvidence(
                relative_path=relative.as_posix(),
                digest=f"sha256:{hashlib.sha256(payload).hexdigest()}",
                size_bytes=len(payload),
                current_head_sha=current_head_sha(root),
                dirty_paths=dirty_paths,
            )
        except ExternalReviewEvidenceError:
            raise
        except (GitOperationError, OSError, UnicodeError, WorkspaceFileSafetyError) as exc:
            raise ExternalReviewEvidenceError(str(exc)) from exc


__all__ = [
    "GitExternalReviewEvidenceAdapter",
    "MAX_EXTERNAL_REVIEW_REPORT_BYTES",
]
