from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import stat

from ..persistence.json_store import write_json_file
from ..persistence.task_repository import load_task_record
from ..workspace.errors import WorkspaceGitError
from ..workspace.git import SubprocessWorkspaceGit
from .local_config import is_local_openai_provider
from .receipt_schema import InvalidLocalAgentReceipt, read_local_agent_receipt


FailureRecorder = Callable[..., None]
ReceiptPersister = Callable[[Path, object, str, str, dict[str, object]], None]
EpisodeRecorder = Callable[[dict[str, object], Path, str, dict[str, object]], None]

MAX_LAST_MESSAGE_BYTES = 1_000_000
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def finalize_default_launch(
    *,
    repo_root: Path,
    config: object,
    task_id: str,
    agent_id: str,
    provider: str,
    exit_code: int,
    output_last_message_path: Path | None,
    receipt_path: Path | None = None,
    workdir: Path | None = None,
    expected_request_digest: str | None = None,
    mark_agent_failed: FailureRecorder,
    persist_receipt: ReceiptPersister | None = None,
) -> int:
    if output_last_message_path is None:
        return exit_code
    receipt = read_receipt(receipt_path)
    try:
        last_message = read_last_message(output_last_message_path)
        if receipt is not None:
            (persist_receipt or persist_local_receipt)(
                repo_root,
                config,
                task_id,
                agent_id,
                receipt,
            )
    finally:
        output_last_message_path.unlink(missing_ok=True)
        if receipt_path is not None:
            receipt_path.unlink(missing_ok=True)

    if exit_code != 0:
        if is_local_openai_provider(provider) and receipt is not None:
            mark_agent_failed(
                repo_root=repo_root,
                config=config,
                task_id=task_id,
                agent_id=agent_id,
                provider=provider,
                error=str(receipt.get("error") or receipt.get("summary") or "local agent failed"),
                last_message=last_message,
            )
        return exit_code

    final_status = classify_last_message(last_message)
    if is_local_openai_provider(provider) and final_status is None:
        mark_agent_failed(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            provider=provider,
            error="local agent did not report a structured final status",
            last_message=last_message,
        )
        return 1
    if final_status == "completed":
        if is_local_openai_provider(provider):
            completion_error = local_completion_error(
                receipt,
                workdir or repo_root,
                expected_request_digest=expected_request_digest,
            )
            if completion_error:
                mark_agent_failed(
                    repo_root=repo_root,
                    config=config,
                    task_id=task_id,
                    agent_id=agent_id,
                    provider=provider,
                    error=completion_error,
                    last_message=last_message,
                )
                return 1
        return 0

    if final_status in {"blocked", "failed"}:
        mark_agent_failed(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            provider=provider,
            error=f"agent reported {final_status}",
            last_message=last_message,
        )
        return 1
    return 0


def read_last_message(output_last_message_path: Path) -> str | None:
    try:
        file_fd = os.open(output_last_message_path, _READ_FLAGS)
    except OSError:
        return None
    try:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_LAST_MESSAGE_BYTES:
            return None
        chunks: list[bytes] = []
        remaining = MAX_LAST_MESSAGE_BYTES + 1
        while remaining > 0:
            chunk = os.read(file_fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > MAX_LAST_MESSAGE_BYTES:
            return None
    finally:
        os.close(file_fd)
    content = payload.decode("utf-8", errors="replace").strip()
    return content or None


def read_receipt(receipt_path: Path | None) -> dict[str, object] | None:
    if receipt_path is None:
        return None
    try:
        return read_local_agent_receipt(receipt_path)
    except InvalidLocalAgentReceipt:
        return None


def local_completion_error(
    receipt: dict[str, object] | None,
    workdir: Path,
    *,
    expected_request_digest: str | None = None,
) -> str | None:
    if receipt is None:
        return "unsupported completion claim: local agent receipt is missing or invalid"
    if (
        receipt.get("schema_version") != "sisyphus.local_agent_run.v1"
        or receipt.get("status") != "completed"
    ):
        return "unsupported completion claim: local agent receipt does not report a completed run"
    actual_request_digest = receipt.get("request_digest")
    if (
        expected_request_digest
        and actual_request_digest is not None
        and actual_request_digest != expected_request_digest
    ):
        return "unsupported completion claim: receipt request digest does not match the launch"
    facts = receipt.get("completion_facts")
    if not isinstance(facts, dict) or facts.get("completion_ready") is not True:
        return "unsupported completion claim: receipt lacks code-and-test completion evidence"
    actual_changes = non_planning_changed_files(workdir)
    if not actual_changes:
        return "unsupported completion claim: no code-level result exists outside .planning"
    mutation_step = facts.get("last_mutation_step")
    test_step = facts.get("last_successful_test_step")
    baseline_step = facts.get("baseline_test_step")
    if (
        type(baseline_step) is not int
        or type(mutation_step) is not int
        or baseline_step >= mutation_step
    ):
        return "unsupported completion claim: no baseline test was recorded before mutation"
    if type(test_step) is not int or test_step <= mutation_step:
        return "unsupported completion claim: no passing test was recorded after the latest mutation"
    receipt_changes = facts.get("changed_files")
    if not isinstance(receipt_changes, list) or not {
        str(path) for path in receipt_changes if isinstance(path, str)
    }.intersection(actual_changes):
        return "unsupported completion claim: receipt changed files do not match the worktree diff"
    return None


def non_planning_changed_files(workdir: Path) -> set[str]:
    try:
        paths = SubprocessWorkspaceGit(workdir, timeout_seconds=10.0).changed_files()
    except (OSError, WorkspaceGitError):
        return set()
    return {
        path
        for path in paths
        if ".planning" not in Path(path).parts and ".git" not in Path(path).parts
    }


def persist_local_receipt(
    repo_root: Path,
    config: object,
    task_id: str,
    agent_id: str,
    receipt: dict[str, object],
    *,
    episode_recorder: EpisodeRecorder | None = None,
) -> None:
    try:
        task, task_file = load_task_record(
            repo_root=repo_root,
            task_dir_name=config.task_dir,
            task_id=task_id,
        )
        path = task_file.parent / "artifacts" / "local-agent" / f"{agent_id}.json"
        write_json_file(path, receipt)
        if episode_recorder is not None:
            episode_recorder(task, task_file.parent, agent_id, receipt)
    except (OSError, UnicodeError, FileNotFoundError):
        return


def classify_last_message(last_message: str | None) -> str | None:
    if not last_message:
        return None
    first_line = last_message.splitlines()[0].strip().lower()
    if first_line == "status: completed":
        return "completed"
    if first_line == "status: blocked":
        return "blocked"
    if first_line == "status: failed":
        return "failed"
    if first_line.startswith("**blocked"):
        return "blocked"
    if first_line.startswith("**failed"):
        return "failed"
    return None


__all__ = [
    "classify_last_message",
    "finalize_default_launch",
    "local_completion_error",
    "non_planning_changed_files",
    "persist_local_receipt",
    "read_last_message",
    "read_receipt",
]
