from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import json

from .config import SisyphusConfig
from .state import list_task_records, load_task_record, save_task_record, utc_now


DEFAULT_CHANGESET_PATH = "CHANGESET.md"
DEFAULT_PROMOTION_RECEIPT_PATH = "artifacts/promotion/merge_receipt.json"


@dataclass(slots=True)
class MergeReceiptOutcome:
    task_id: str
    branch: str | None
    pr_number: int
    title: str
    recorded_at: str
    receipt_path: Path
    changeset_path: Path


def record_merged_pull_request(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    pr_number: int,
    title: str,
    task_id: str | None = None,
    branch: str | None = None,
    repo_full_name: str | None = None,
    url: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    head_sha: str | None = None,
    merge_commit_sha: str | None = None,
    merged_at: str | None = None,
    merged_by: str | None = None,
    merge_method: str | None = None,
    additions: int | None = None,
    deletions: int | None = None,
    changed_files: list[dict[str, object]] | None = None,
) -> MergeReceiptOutcome:
    if pr_number < 1:
        raise ValueError("pr_number must be a positive integer")

    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("title must be non-empty")

    task, task_file = _resolve_task(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        branch=branch,
        head_branch=head_branch,
    )
    recorded_at = utc_now()
    normalized_changed_files = _normalize_changed_files(changed_files)
    total_additions = _resolve_total_count(additions, normalized_changed_files, "additions")
    total_deletions = _resolve_total_count(deletions, normalized_changed_files, "deletions")

    task_dir = repo_root / str(task["task_dir"])
    docs = dict(task.get("docs", {}))
    receipt_relative_path = Path(str(docs.get("promotion") or DEFAULT_PROMOTION_RECEIPT_PATH))
    changeset_relative_path = Path(str(docs.get("changeset") or DEFAULT_CHANGESET_PATH))
    receipt_path = task_dir / receipt_relative_path
    changeset_path = task_dir / changeset_relative_path

    receipt = {
        "recorded_at": recorded_at,
        "task_id": task["id"],
        "task_branch": task.get("branch"),
        "base_branch": base_branch or task.get("base_branch"),
        "repo_full_name": repo_full_name,
        "pull_request": {
            "number": pr_number,
            "title": normalized_title,
            "url": url,
            "head_branch": head_branch or branch or task.get("branch"),
            "head_sha": head_sha,
            "merge_commit_sha": merge_commit_sha,
            "merged_at": merged_at,
            "merged_by": merged_by,
            "merge_method": merge_method,
        },
        "changes": {
            "file_count": len(normalized_changed_files),
            "additions": total_additions,
            "deletions": total_deletions,
            "files": normalized_changed_files,
        },
    }

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    changeset_path.parent.mkdir(parents=True, exist_ok=True)
    changeset_path.write_text(_render_changeset_markdown(receipt), encoding="utf-8")

    task.setdefault("meta", {})
    task["meta"]["promotion"] = {
        "status": "merged",
        "recorded_at": recorded_at,
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "title": normalized_title,
        "url": url,
        "head_branch": head_branch or branch or task.get("branch"),
        "base_branch": base_branch or task.get("base_branch"),
        "head_sha": head_sha,
        "merge_commit_sha": merge_commit_sha,
        "merged_at": merged_at,
        "merged_by": merged_by,
        "merge_method": merge_method,
        "receipt_path": str(receipt_relative_path),
        "changeset_path": str(changeset_relative_path),
    }
    save_task_record(task_file=task_file, task=task)

    return MergeReceiptOutcome(
        task_id=str(task["id"]),
        branch=str(task.get("branch")) if task.get("branch") else None,
        pr_number=pr_number,
        title=normalized_title,
        recorded_at=recorded_at,
        receipt_path=receipt_path,
        changeset_path=changeset_path,
    )


def _resolve_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str | None,
    branch: str | None,
    head_branch: str | None,
) -> tuple[dict, Path]:
    if task_id:
        task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
        expected_branch = (branch or head_branch or "").strip()
        if expected_branch and str(task.get("branch") or "") != expected_branch:
            raise ValueError(f"task `{task_id}` does not match branch `{expected_branch}`")
        return task, task_file

    branch_name = (branch or head_branch or "").strip()
    if not branch_name:
        raise ValueError("merged pull request requires task_id or branch/head_branch")

    for candidate in list_task_records(repo_root=repo_root, task_dir_name=config.task_dir):
        if str(candidate.get("branch") or "") != branch_name:
            continue
        return load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=str(candidate["id"]))

    raise FileNotFoundError(f"no task found for branch `{branch_name}`")


def _normalize_changed_files(changed_files: list[dict[str, object]] | None) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_item in changed_files or []:
        if not isinstance(raw_item, Mapping):
            raise TypeError("changed_files entries must be mapping objects")
        path = str(raw_item.get("path", "")).strip()
        if not path:
            raise ValueError("changed_files entries require a non-empty `path`")
        item: dict[str, object] = {"path": path}
        status = str(raw_item.get("status", "modified")).strip() or "modified"
        item["status"] = status
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


def _coerce_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _resolve_total_count(
    explicit_value: int | None,
    changed_files: list[dict[str, object]],
    key: str,
) -> int | None:
    if explicit_value is not None:
        return explicit_value
    values = [int(item[key]) for item in changed_files if isinstance(item.get(key), int)]
    if not values:
        return None
    return sum(values)


def _render_changeset_markdown(receipt: Mapping[str, object]) -> str:
    pull_request = dict(receipt.get("pull_request", {})) if isinstance(receipt.get("pull_request"), Mapping) else {}
    changes = dict(receipt.get("changes", {})) if isinstance(receipt.get("changes"), Mapping) else {}
    files = list(changes.get("files", [])) if isinstance(changes.get("files"), list) else []
    pr_number = pull_request.get("number")
    title = str(pull_request.get("title", "")).strip()
    url = str(pull_request.get("url", "")).strip()
    repo_full_name = str(receipt.get("repo_full_name", "")).strip()
    task_id = str(receipt.get("task_id", "")).strip()
    task_branch = str(receipt.get("task_branch", "")).strip()
    base_branch = str(receipt.get("base_branch", "")).strip()
    head_branch = str(pull_request.get("head_branch", "")).strip()
    merge_commit_sha = str(pull_request.get("merge_commit_sha", "")).strip()
    merged_at = str(pull_request.get("merged_at", "")).strip()
    merge_method = str(pull_request.get("merge_method", "")).strip()
    merged_by = str(pull_request.get("merged_by", "")).strip()
    file_count = changes.get("file_count")
    additions = changes.get("additions")
    deletions = changes.get("deletions")

    lines = [
        "# Changeset",
        "",
        "## Merge",
        "",
        f"- Task: `{task_id}`",
    ]
    if pr_number is not None:
        if url:
            lines.append(f"- Pull Request: [#{pr_number}]({url})")
        else:
            lines.append(f"- Pull Request: `#{pr_number}`")
    if title:
        lines.append(f"- Title: {title}")
    if repo_full_name:
        lines.append(f"- Repository: `{repo_full_name}`")
    if task_branch:
        lines.append(f"- Task Branch: `{task_branch}`")
    if head_branch or base_branch:
        lines.append(f"- Merge Target: `{head_branch or task_branch}` -> `{base_branch}`")
    if merge_commit_sha:
        lines.append(f"- Merge Commit: `{merge_commit_sha}`")
    if merge_method:
        lines.append(f"- Merge Method: `{merge_method}`")
    if merged_by:
        lines.append(f"- Merged By: `{merged_by}`")
    if merged_at:
        lines.append(f"- Merged At: `{merged_at}`")
    if file_count is not None or additions is not None or deletions is not None:
        summary_bits: list[str] = []
        if file_count is not None:
            summary_bits.append(f"{file_count} files")
        if additions is not None:
            summary_bits.append(f"+{additions}")
        if deletions is not None:
            summary_bits.append(f"-{deletions}")
        lines.append(f"- Diff Summary: {', '.join(summary_bits)}")

    lines.extend(["", "## Changed Paths", ""])
    if files:
        for raw_item in files:
            if not isinstance(raw_item, Mapping):
                continue
            path = str(raw_item.get("path", "")).strip()
            status = str(raw_item.get("status", "modified")).strip() or "modified"
            previous_path = str(raw_item.get("previous_path", "")).strip()
            additions = raw_item.get("additions")
            deletions = raw_item.get("deletions")
            details: list[str] = [status]
            if previous_path:
                details.append(f"from {previous_path}")
            if additions is not None or deletions is not None:
                change_bits: list[str] = []
                if additions is not None:
                    change_bits.append(f"+{additions}")
                if deletions is not None:
                    change_bits.append(f"-{deletions}")
                details.append(", ".join(change_bits))
            lines.append(f"- `{path}` ({'; '.join(details)})")
    else:
        lines.append("- No changed file details were provided.")

    top_level_counts = _top_level_path_counts(files)
    if top_level_counts:
        lines.extend(["", "## Scope", ""])
        for root, count in sorted(top_level_counts.items()):
            lines.append(f"- `{root}`: {count} files")

    lines.append("")
    return "\n".join(lines)


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
