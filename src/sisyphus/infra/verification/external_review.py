from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import hashlib
import json
import re

from ...application.ports.review import (
    ExternalReviewEvidence,
    ExternalReviewEvidenceError,
    ExternalReviewFinding,
    ExternalReviewScopeEvidence,
)
from ...application.review_scope import (
    external_review_artifact_prefix,
    external_review_scope_digest,
    external_review_scope_document_paths,
)
from ...gitops import GitOperationError, current_head_sha, list_dirty_paths
from ..workspace import SecureWorkspaceFiles
from ..workspace.errors import WorkspaceFileSafetyError


MAX_EXTERNAL_REVIEW_ENVELOPE_BYTES = 256 * 1024
MAX_EXTERNAL_REVIEW_REPORT_BYTES = 1024 * 1024
MAX_EXTERNAL_REVIEW_SCOPE_DOCUMENT_BYTES = 2 * 1024 * 1024
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
_ENVELOPE_FIELDS = {
    "schema_version",
    "provider",
    "reviewer",
    "reviewed_head_sha",
    "scope_digest",
    "report",
    "summary",
    "findings",
}
_REPORT_FIELDS = {"path", "digest"}
_FINDING_FIELDS = {"id", "severity", "title", "detail", "blocking"}
_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


class GitExternalReviewEvidenceAdapter:
    def scope(
        self,
        workspace: str,
        task: Mapping[str, object],
    ) -> ExternalReviewScopeEvidence:
        root = _workspace_root(workspace)
        try:
            files = SecureWorkspaceFiles(root)
            document_digests: dict[str, str | None] = {}
            for relative_path in external_review_scope_document_paths(task):
                try:
                    content = files.read_text(
                        PurePosixPath(relative_path),
                        max_bytes=MAX_EXTERNAL_REVIEW_SCOPE_DOCUMENT_BYTES,
                    )
                except FileNotFoundError:
                    document_digests[relative_path] = None
                else:
                    document_digests[relative_path] = _digest(content.encode("utf-8"))
            return ExternalReviewScopeEvidence(
                current_head_sha=current_head_sha(root).lower(),
                scope_digest=external_review_scope_digest(task, document_digests),
                document_digests=tuple(sorted(document_digests.items())),
            )
        except ExternalReviewEvidenceError:
            raise
        except (GitOperationError, OSError, UnicodeError, ValueError, WorkspaceFileSafetyError) as exc:
            raise ExternalReviewEvidenceError(str(exc)) from exc

    def inspect(
        self,
        workspace: str,
        envelope_path: str,
        task: Mapping[str, object],
    ) -> ExternalReviewEvidence:
        root = _workspace_root(workspace)
        try:
            files = SecureWorkspaceFiles(root)
            prefix = external_review_artifact_prefix(task)
            normalized_envelope_path = _review_artifact_path(
                envelope_path,
                prefix=prefix,
                suffix=".json",
                field="envelope_path",
            )
            envelope_text = files.read_text(
                PurePosixPath(normalized_envelope_path),
                max_bytes=MAX_EXTERNAL_REVIEW_ENVELOPE_BYTES,
            )
            envelope_payload = envelope_text.encode("utf-8")
            envelope = _parse_envelope(envelope_text, artifact_prefix=prefix)

            report_path = str(envelope["report_path"])
            if report_path == normalized_envelope_path:
                raise ValueError("external review envelope and report paths must differ")
            report_text = files.read_text(
                PurePosixPath(report_path),
                max_bytes=MAX_EXTERNAL_REVIEW_REPORT_BYTES,
            )
            if not report_text.strip():
                raise ValueError("external review report must be non-empty")
            report_payload = report_text.encode("utf-8")
            report_digest = _digest(report_payload)
            if report_digest != envelope["report_digest"]:
                raise ValueError("external review report digest does not match the envelope")

            scope = self.scope(workspace, task)
            changed_paths, deleted_paths = list_dirty_paths(root)
            dirty_paths = tuple(sorted({*changed_paths, *deleted_paths}))
            return ExternalReviewEvidence(
                envelope_path=normalized_envelope_path,
                envelope_digest=_digest(envelope_payload),
                envelope_size_bytes=len(envelope_payload),
                provider=str(envelope["provider"]),
                reviewer=str(envelope["reviewer"]),
                reviewed_head_sha=str(envelope["reviewed_head_sha"]),
                scope_digest=str(envelope["scope_digest"]),
                report_path=report_path,
                report_digest=report_digest,
                report_size_bytes=len(report_payload),
                summary=str(envelope["summary"]),
                findings=tuple(envelope["findings"]),
                current_head_sha=scope.current_head_sha,
                current_scope_digest=scope.scope_digest,
                document_digests=scope.document_digests,
                dirty_paths=dirty_paths,
            )
        except ExternalReviewEvidenceError:
            raise
        except (
            GitOperationError,
            json.JSONDecodeError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
            WorkspaceFileSafetyError,
        ) as exc:
            raise ExternalReviewEvidenceError(str(exc)) from exc


def _parse_envelope(
    content: str,
    *,
    artifact_prefix: str,
) -> dict[str, object]:
    raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
    envelope = _strict_mapping(raw, field="envelope", expected=_ENVELOPE_FIELDS)
    if envelope["schema_version"] != "sisyphus.external_review.v1":
        raise ValueError("unsupported external review envelope schema_version")
    provider = _single_line_text(envelope["provider"], field="provider", max_length=256)
    reviewer = _single_line_text(envelope["reviewer"], field="reviewer", max_length=256)
    reviewed_head_sha = _bounded_text(
        envelope["reviewed_head_sha"],
        field="reviewed_head_sha",
        max_length=64,
    ).lower()
    if not _GIT_SHA_PATTERN.fullmatch(reviewed_head_sha):
        raise ValueError("reviewed_head_sha must be a 40-64 character hexadecimal Git object ID")
    scope_digest = _validated_digest(envelope["scope_digest"], field="scope_digest")
    summary = _bounded_text(envelope["summary"], field="summary", max_length=4_000)

    report = _strict_mapping(envelope["report"], field="report", expected=_REPORT_FIELDS)
    report_path = _review_artifact_path(
        report["path"],
        prefix=artifact_prefix,
        suffix=".md",
        field="report.path",
    )
    report_digest = _validated_digest(report["digest"], field="report.digest")

    findings_raw = envelope["findings"]
    if not isinstance(findings_raw, list):
        raise TypeError("findings must be an array")
    if len(findings_raw) > 100:
        raise ValueError("findings cannot contain more than 100 entries")
    findings: list[ExternalReviewFinding] = []
    finding_ids: set[str] = set()
    for index, item in enumerate(findings_raw):
        field = f"findings[{index}]"
        finding = _strict_mapping(item, field=field, expected=_FINDING_FIELDS)
        finding_id = _bounded_text(finding["id"], field=f"{field}.id", max_length=128)
        if not _IDENTIFIER_PATTERN.fullmatch(finding_id):
            raise ValueError(f"{field}.id contains unsupported characters")
        if finding_id in finding_ids:
            raise ValueError(f"duplicate external review finding id: {finding_id}")
        finding_ids.add(finding_id)
        severity = _bounded_text(
            finding["severity"],
            field=f"{field}.severity",
            max_length=2,
        ).upper()
        if severity not in _SEVERITIES:
            raise ValueError(f"{field}.severity must be one of P0, P1, P2, or P3")
        blocking = finding["blocking"]
        if not isinstance(blocking, bool):
            raise TypeError(f"{field}.blocking must be a boolean")
        if severity in {"P0", "P1"} and not blocking:
            raise ValueError(f"{field} severity {severity} must be blocking")
        findings.append(
            ExternalReviewFinding(
                finding_id=finding_id,
                severity=severity,
                title=_single_line_text(
                    finding["title"],
                    field=f"{field}.title",
                    max_length=512,
                ),
                detail=_bounded_text(
                    finding["detail"],
                    field=f"{field}.detail",
                    max_length=4_000,
                ),
                blocking=blocking,
            )
        )
    return {
        "provider": provider,
        "reviewer": reviewer,
        "reviewed_head_sha": reviewed_head_sha,
        "scope_digest": scope_digest,
        "report_path": report_path,
        "report_digest": report_digest,
        "summary": summary,
        "findings": tuple(findings),
    }


def _strict_mapping(
    value: object,
    *,
    field: str,
    expected: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} must be an object")
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise ValueError(f"{field} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{field} contains unknown fields: {', '.join(unknown)}")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _review_artifact_path(
    value: object,
    *,
    prefix: str,
    suffix: str,
    field: str,
) -> str:
    raw = _bounded_text(value, field=field, max_length=4_096)
    if "\\" in raw or "\x00" in raw:
        raise ValueError(f"{field} must be a relative POSIX path")
    path = PurePosixPath(raw)
    prefix_path = PurePosixPath(prefix)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != raw
        or any(part in {"", "."} for part in path.parts)
        or path.suffix.lower() != suffix
        or path.parent != prefix_path
    ):
        raise ValueError(
            f"{field} must be a normalized {suffix} file directly under {prefix}/"
        )
    return path.as_posix()


def _validated_digest(value: object, *, field: str) -> str:
    digest = _bounded_text(value, field=field, max_length=71).lower()
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise ValueError(f"{field} must be a sha256 digest")
    return digest


def _bounded_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must be non-empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return normalized


def _single_line_text(value: object, *, field: str, max_length: int) -> str:
    normalized = _bounded_text(value, field=field, max_length=max_length)
    if any(character in normalized for character in ("\r", "\n", "\x00")):
        raise ValueError(f"{field} must be a single line")
    return normalized


def _workspace_root(workspace: str) -> Path:
    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir():
        raise ExternalReviewEvidenceError(f"task worktree does not exist: {workspace}")
    return root


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


__all__ = [
    "GitExternalReviewEvidenceAdapter",
    "MAX_EXTERNAL_REVIEW_ENVELOPE_BYTES",
    "MAX_EXTERNAL_REVIEW_REPORT_BYTES",
    "MAX_EXTERNAL_REVIEW_SCOPE_DOCUMENT_BYTES",
]
