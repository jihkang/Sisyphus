from __future__ import annotations

from collections.abc import Mapping
import re

from .commands.promotion import RecordMergedPullRequestCommand
from .ports.workflow import TaskRecord


DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH = "artifacts/promotion/open_pr_receipt.json"


def build_execution_receipt(
    task: TaskRecord,
    *,
    draft: bool,
    written_at: str,
) -> dict[str, object]:
    promotion = dict(task.get("promotion", {}))
    return {
        "written_at": written_at,
        "task_id": task.get("id"),
        "task_branch": task.get("branch"),
        "status": promotion.get("status"),
        "repo_full_name": promotion.get("repo_full_name"),
        "remote_name": promotion.get("remote_name"),
        "base_branch": promotion.get("base_branch"),
        "base_resolution": {
            "strategy": promotion.get("strategy"),
            "source": promotion.get("base_source"),
            "reason": promotion.get("base_reason"),
            "parent_task_id": promotion.get("parent_task_id"),
            "parent_artifact_id": promotion.get("parent_artifact_id"),
            "parent_branch": promotion.get("resolved_parent_branch"),
        },
        "head_branch": promotion.get("head_branch"),
        "commit": {
            "message": promotion.get("commit_message"),
            "sha": promotion.get("head_sha"),
            "committed_at": promotion.get("committed_at"),
        },
        "push": {"pushed_at": promotion.get("pushed_at")},
        "pull_request": {
            "number": promotion.get("pr_number"),
            "url": promotion.get("pr_url"),
            "title": promotion.get("title"),
            "opened_at": promotion.get("pr_opened_at"),
            "draft": draft,
        },
    }


def build_merge_receipt(
    task: TaskRecord,
    command: RecordMergedPullRequestCommand,
    *,
    title: str,
    recorded_at: str,
    changed_files: list[dict[str, object]],
    additions: int | None,
    deletions: int | None,
) -> dict[str, object]:
    promotion = task["promotion"]
    return {
        "recorded_at": recorded_at,
        "task_id": task["id"],
        "task_branch": task.get("branch"),
        "base_branch": command.base_branch or task.get("base_branch"),
        "repo_full_name": command.repo_full_name,
        "pull_request": {
            "number": command.pr_number,
            "title": title,
            "url": command.url,
            "head_branch": command.head_branch or command.branch or task.get("branch"),
            "head_sha": command.head_sha,
            "merge_commit_sha": command.merge_commit_sha,
            "merged_at": command.merged_at,
            "merged_by": command.merged_by,
            "merge_method": command.merge_method,
        },
        "base_resolution": {
            "strategy": promotion.get("strategy"),
            "source": promotion.get("base_source"),
            "reason": promotion.get("base_reason"),
            "parent_task_id": promotion.get("parent_task_id"),
            "parent_artifact_id": promotion.get("parent_artifact_id"),
            "parent_branch": promotion.get("resolved_parent_branch"),
        },
        "changes": {
            "file_count": len(changed_files),
            "additions": additions,
            "deletions": deletions,
            "files": changed_files,
        },
    }


def normalize_changed_files(
    changed_files: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_item in changed_files:
        if not isinstance(raw_item, Mapping):
            raise TypeError("changed_files entries must be mapping objects")
        path = str(raw_item.get("path", "")).strip()
        if not path:
            raise ValueError("changed_files entries require a non-empty `path`")
        item: dict[str, object] = {
            "path": path,
            "status": str(raw_item.get("status", "modified")).strip() or "modified",
        }
        previous_path = str(raw_item.get("previous_path", "")).strip()
        if previous_path:
            item["previous_path"] = previous_path
        additions = _coerce_optional_int(raw_item.get("additions"))
        deletions = _coerce_optional_int(raw_item.get("deletions"))
        if additions is not None:
            item["additions"] = additions
        if deletions is not None:
            item["deletions"] = deletions
        normalized.append(item)
    return normalized


def resolve_total_count(
    explicit_value: int | None,
    changed_files: list[dict[str, object]],
    key: str,
) -> int | None:
    if explicit_value is not None:
        return explicit_value
    values = [int(item[key]) for item in changed_files if isinstance(item.get(key), int)]
    return sum(values) if values else None


def render_changeset_markdown(receipt: Mapping[str, object]) -> str:
    pull_request = dict(receipt.get("pull_request", {}))
    changes = dict(receipt.get("changes", {}))
    files = list(changes.get("files", []))
    lines = ["# Changeset", "", "## Merge", "", f"- Task: `{receipt.get('task_id', '')}`"]
    pr_number = pull_request.get("number")
    url = str(pull_request.get("url") or "")
    if pr_number is not None:
        lines.append(f"- Pull Request: [#{pr_number}]({url})" if url else f"- Pull Request: `#{pr_number}`")
    fields = [
        ("Title", pull_request.get("title")),
        ("Repository", receipt.get("repo_full_name")),
        ("Task Branch", receipt.get("task_branch")),
    ]
    for label, value in fields:
        if value:
            rendered = str(value)
            lines.append(f"- {label}: {rendered}" if label == "Title" else f"- {label}: `{rendered}`")
    head = str(pull_request.get("head_branch") or receipt.get("task_branch") or "")
    base = str(receipt.get("base_branch") or "")
    if head or base:
        lines.append(f"- Merge Target: `{head}` -> `{base}`")
    for label, key in [
        ("Merge Commit", "merge_commit_sha"),
        ("Merge Method", "merge_method"),
        ("Merged By", "merged_by"),
        ("Merged At", "merged_at"),
    ]:
        if pull_request.get(key):
            lines.append(f"- {label}: `{pull_request[key]}`")
    summary: list[str] = []
    if changes.get("file_count") is not None:
        summary.append(f"{changes['file_count']} files")
    if changes.get("additions") is not None:
        summary.append(f"+{changes['additions']}")
    if changes.get("deletions") is not None:
        summary.append(f"-{changes['deletions']}")
    if summary:
        lines.append(f"- Diff Summary: {', '.join(summary)}")
    lines.extend(["", "## Changed Paths", ""])
    if files:
        for raw_item in files:
            if not isinstance(raw_item, Mapping):
                continue
            details = [str(raw_item.get("status") or "modified")]
            if raw_item.get("previous_path"):
                details.append(f"from {raw_item['previous_path']}")
            counts: list[str] = []
            if raw_item.get("additions") is not None:
                counts.append(f"+{raw_item['additions']}")
            if raw_item.get("deletions") is not None:
                counts.append(f"-{raw_item['deletions']}")
            if counts:
                details.append(", ".join(counts))
            lines.append(f"- `{raw_item.get('path', '')}` ({'; '.join(details)})")
    else:
        lines.append("- No changed file details were provided.")
    counts = _top_level_path_counts(files)
    if counts:
        lines.extend(["", "## Scope", ""])
        for root, count in sorted(counts.items()):
            lines.append(f"- `{root}`: {count} files")
    lines.append("")
    return "\n".join(lines)


def task_has_open_pr(task: TaskRecord) -> bool:
    promotion = task.get("promotion", {})
    return (
        isinstance(promotion, dict)
        and promotion.get("pr_number") not in (None, "")
        and bool(str(promotion.get("pr_url") or "").strip())
    )


def default_promotion_title(task: Mapping[str, object]) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "task").strip().replace("-", " ")
    return f"{task_id}: {slug}" if task_id else (slug or "Sisyphus promotion")


def default_commit_message(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    return f"{task_id}: {title}" if task_id else title


def default_promotion_body(task: Mapping[str, object], *, title: str) -> str:
    task_id = str(task.get("id") or "").strip()
    slug = str(task.get("slug") or "").strip()
    verify_status = str(task.get("verify_status") or "not_run").strip() or "not_run"
    lines = ["## Summary", "", f"- Promote task `{task_id}`"]
    if slug:
        lines.append(f"- Slug: `{slug}`")
    lines.extend(
        [
            f"- Verify status: `{verify_status}`",
            "",
            "## Notes",
            "",
            f"- Title: {title}",
            "- Generated by Sisyphus promotion executor",
            "",
        ]
    )
    return "\n".join(lines)


def pull_request_number_from_url(url: str | None) -> int | None:
    match = re.search(r"/pull/(\d+)(?:$|[?#])", str(url or ""))
    return int(match.group(1)) if match else None


def repo_full_name_from_remote_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if normalized.startswith("git@github.com:"):
        repo = normalized.split(":", 1)[1]
    elif "github.com/" in normalized:
        repo = normalized.split("github.com/", 1)[1]
    else:
        return None
    repo = repo.strip().rstrip("/")
    return (repo[:-4] if repo.endswith(".git") else repo) or None


def optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _coerce_optional_int(value: object) -> int | None:
    return None if value in (None, "") else int(value)


def _top_level_path_counts(files: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_item in files:
        if not isinstance(raw_item, Mapping):
            continue
        path = str(raw_item.get("path", "")).strip()
        if not path:
            continue
        root = path.split("/", 1)[0]
        if "." in root and "/" not in path:
            root = "(repo root files)"
        counts[root] = counts.get(root, 0) + 1
    return counts


__all__ = [
    "DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH",
    "build_execution_receipt",
    "build_merge_receipt",
    "default_commit_message",
    "default_promotion_body",
    "default_promotion_title",
    "normalize_changed_files",
    "optional_text",
    "pull_request_number_from_url",
    "render_changeset_markdown",
    "repo_full_name_from_remote_url",
    "resolve_total_count",
    "task_has_open_pr",
]
