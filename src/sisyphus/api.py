from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import SisyphusConfig, load_config
from .daemon import process_inbox_event, queue_conversation_event, queue_pull_request_merged_event
from .paths import inbox_failed_dir, inbox_processed_dir
from .state import list_task_records, load_task_record
from .workflow import run_workflow_cycle


@dataclass(slots=True)
class QueuedConversation:
    event: dict
    event_path: Path

    @property
    def event_id(self) -> str:
        return str(self.event["id"])


@dataclass(slots=True)
class TaskRequestResult:
    event_id: str
    event_status: str
    event_path: Path
    task_id: str | None
    task: dict | None
    orchestrated: int
    error: str | None
    processed_event: dict

    @property
    def ok(self) -> bool:
        return self.error is None and self.event_status == "processed"


@dataclass(slots=True)
class QueuedPullRequestMerge:
    event: dict
    event_path: Path

    @property
    def event_id(self) -> str:
        return str(self.event["id"])


@dataclass(slots=True)
class MergeRecordResult:
    event_id: str
    event_status: str
    event_path: Path
    task_id: str | None
    pr_number: int | None
    receipt_path: Path | None
    changeset_path: Path | None
    error: str | None
    processed_event: dict

    @property
    def ok(self) -> bool:
        return self.error is None and self.event_status == "processed"


def queue_conversation(
    repo_root: Path,
    *,
    message: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    source_context: dict[str, object] | None = None,
    adopt_current_changes: bool = False,
    adopt_paths: list[str] | None = None,
    auto_run: bool = True,
) -> QueuedConversation:
    event, event_path = queue_conversation_event(
        repo_root=repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        source_context=source_context,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=auto_run,
    )
    return QueuedConversation(event=event, event_path=event_path)


def request_task(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    message: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    source_context: dict[str, object] | None = None,
    adopt_current_changes: bool = False,
    adopt_paths: list[str] | None = None,
    auto_run: bool = True,
) -> TaskRequestResult:
    effective_config = config or load_config(repo_root)
    queued = queue_conversation(
        repo_root=repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        source_context=source_context,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=auto_run,
    )

    processed_event = process_inbox_event(
        repo_root=repo_root,
        config=effective_config,
        event_path=queued.event_path,
    )
    orchestrated = 0
    if processed_event.get("status") == "processed" and auto_run:
        orchestrated = run_until_stable(repo_root=repo_root, config=effective_config)

    task_id = None
    task = None
    result = processed_event.get("result") or {}
    if isinstance(result, dict):
        task_id = result.get("task_id")
    if task_id:
        task, _ = load_task_record(repo_root=repo_root, task_dir_name=effective_config.task_dir, task_id=str(task_id))

    return TaskRequestResult(
        event_id=queued.event_id,
        event_status=str(processed_event.get("status")),
        event_path=_processed_event_path(repo_root=repo_root, event_id=queued.event_id, status=str(processed_event.get("status"))),
        task_id=str(task_id) if task_id else None,
        task=task,
        orchestrated=orchestrated,
        error=processed_event.get("error"),
        processed_event=processed_event,
    )


def queue_pull_request_merged(
    repo_root: Path,
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
) -> QueuedPullRequestMerge:
    event, event_path = queue_pull_request_merged_event(
        repo_root=repo_root,
        task_id=task_id,
        branch=branch,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        title=title,
        url=url,
        base_branch=base_branch,
        head_branch=head_branch,
        head_sha=head_sha,
        merge_commit_sha=merge_commit_sha,
        merged_at=merged_at,
        merged_by=merged_by,
        merge_method=merge_method,
        additions=additions,
        deletions=deletions,
        changed_files=changed_files,
    )
    return QueuedPullRequestMerge(event=event, event_path=event_path)


def record_merged_pull_request(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
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
) -> MergeRecordResult:
    effective_config = config or load_config(repo_root)
    queued = queue_pull_request_merged(
        repo_root=repo_root,
        task_id=task_id,
        branch=branch,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        title=title,
        url=url,
        base_branch=base_branch,
        head_branch=head_branch,
        head_sha=head_sha,
        merge_commit_sha=merge_commit_sha,
        merged_at=merged_at,
        merged_by=merged_by,
        merge_method=merge_method,
        additions=additions,
        deletions=deletions,
        changed_files=changed_files,
    )

    processed_event = process_inbox_event(
        repo_root=repo_root,
        config=effective_config,
        event_path=queued.event_path,
    )
    result = processed_event.get("result") if isinstance(processed_event.get("result"), dict) else {}
    task_id_result = result.get("task_id")
    pr_number_result = result.get("pr_number")
    receipt_path = Path(result["receipt_path"]) if result.get("receipt_path") else None
    changeset_path = Path(result["changeset_path"]) if result.get("changeset_path") else None

    return MergeRecordResult(
        event_id=queued.event_id,
        event_status=str(processed_event.get("status")),
        event_path=_processed_event_path(repo_root=repo_root, event_id=queued.event_id, status=str(processed_event.get("status"))),
        task_id=str(task_id_result) if task_id_result else None,
        pr_number=int(pr_number_result) if pr_number_result is not None else None,
        receipt_path=receipt_path,
        changeset_path=changeset_path,
        error=processed_event.get("error"),
        processed_event=processed_event,
    )


def run_until_stable(repo_root: Path, *, config: SisyphusConfig | None = None) -> int:
    effective_config = config or load_config(repo_root)
    orchestrated = 0
    while True:
        progressed = run_workflow_cycle(repo_root=repo_root, config=effective_config)
        if progressed == 0:
            return orchestrated
        orchestrated += progressed


def get_task(repo_root: Path, task_id: str, *, config: SisyphusConfig | None = None) -> dict:
    effective_config = config or load_config(repo_root)
    task, _ = load_task_record(repo_root=repo_root, task_dir_name=effective_config.task_dir, task_id=task_id)
    return task


def list_tasks(repo_root: Path, *, config: SisyphusConfig | None = None) -> list[dict]:
    effective_config = config or load_config(repo_root)
    return list_task_records(repo_root=repo_root, task_dir_name=effective_config.task_dir)


def _processed_event_path(*, repo_root: Path, event_id: str, status: str) -> Path:
    filename = f"{event_id}.json"
    if status == "processed":
        return inbox_processed_dir(repo_root) / filename
    if status == "failed":
        return inbox_failed_dir(repo_root) / filename
    return inbox_processed_dir(repo_root) / filename
