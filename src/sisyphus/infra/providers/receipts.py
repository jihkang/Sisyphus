from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

from ...providers.local_openai import is_local_openai_provider
from ..workspace.errors import WorkspaceGitError
from ..workspace.git import SubprocessWorkspaceGit


FailureRecorder = Callable[..., None]
ReceiptPersister = Callable[[Path, object, str, str, dict[str, object]], None]


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
            completion_error = local_completion_error(receipt, workdir or repo_root)
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
    if not output_last_message_path.exists():
        return None
    content = output_last_message_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).strip()
    return content or None


def read_receipt(receipt_path: Path | None) -> dict[str, object] | None:
    if receipt_path is None or not receipt_path.exists():
        return None
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def local_completion_error(
    receipt: dict[str, object] | None,
    workdir: Path,
) -> str | None:
    if receipt is None:
        return "unsupported completion claim: local agent receipt is missing or invalid"
    if (
        receipt.get("schema_version") != "sisyphus.local_agent_run.v1"
        or receipt.get("status") != "completed"
    ):
        return "unsupported completion claim: local agent receipt does not report a completed run"
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
) -> None:
    try:
        from ...state import load_task_record

        task, task_file = load_task_record(
            repo_root=repo_root,
            task_dir_name=config.task_dir,
            task_id=task_id,
        )
        path = task_file.parent / "artifacts" / "local-agent" / f"{agent_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        append_local_episode_steps(task, task_file.parent, agent_id, receipt)
    except (OSError, UnicodeError, FileNotFoundError):
        return


def append_local_episode_steps(
    task: dict[str, object],
    task_dir: Path,
    agent_id: str,
    receipt: dict[str, object],
) -> None:
    from ...episode_trace import (
        append_episode_step,
        build_episode_step,
        default_episode_id,
        next_episode_step,
    )
    from ...observation import build_task_observation

    raw_events = receipt.get("events")
    if not isinstance(raw_events, list):
        return
    events = [event for event in raw_events if isinstance(event, dict) and event.get("action")]
    if not events:
        return
    episode_id = default_episode_id(str(task.get("id") or "unknown"), actor_id=agent_id)
    observation = build_task_observation(task, task_dir)
    state = dict(task)
    step_number = next_episode_step(task_dir, episode_id)
    for event in events:
        action_name = str(event.get("action") or "unknown")
        arguments = event.get("arguments") if isinstance(event.get("arguments"), dict) else {}
        test_first_phase = event.get("test_first_phase")
        if isinstance(test_first_phase, str):
            arguments = {**arguments, "test_first_phase": test_first_phase}
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        result_payload = {
            "ok": bool(event.get("ok")),
            "blocked": bool(event.get("blocked")),
            **result,
        }
        episode_step = build_episode_step(
            episode_id=episode_id,
            task_id=str(task.get("id") or ""),
            step=step_number,
            observation=observation,
            action_name=f"local_agent.{action_name}",
            arguments=arguments,
            result=result_payload,
            state_before=state,
            state_after=state,
            actor={"interface": "local_provider", "agent_id": agent_id},
        )
        append_episode_step(task_dir, episode_step)
        step_number += 1


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
    "append_local_episode_steps",
    "classify_last_message",
    "finalize_default_launch",
    "local_completion_error",
    "non_planning_changed_files",
    "persist_local_receipt",
    "read_last_message",
    "read_receipt",
]
