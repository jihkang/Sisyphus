from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .agents import AgentTrackingError, update_agent
from .codex_prompt import build_codex_prompt, build_local_worker_prompt
from .config import load_config
from .discovery import detect_repo_root
from .providers.local_openai import (
    LocalProviderConfig,
    LocalProviderConfigError,
    build_worker_command as build_local_worker_command,
    is_local_openai_provider,
    local_provider_available,
    parse_local_provider_args,
)


@dataclass(frozen=True, slots=True)
class ProviderLaunch:
    command: list[str]
    stdin_text: str | None
    step: str
    summary: str
    env: dict[str, str]
    output_last_message_path: Path
    effective_provider: str
    workdir: Path
    receipt_path: Path | None = None


def run_provider_wrapper(provider: str, argv: list[str], *, repo_root: Path | None = None) -> int:
    from .cli import handle_agent_run

    repo_root = repo_root or detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    normalized_argv = _normalize_wrapper_argv(argv)
    parser = argparse.ArgumentParser(prog=f"{provider}-agent-wrapper")
    subparsers = parser.add_subparsers(dest="launch_mode", required=True)

    task_parser = subparsers.add_parser("task")
    task_parser.add_argument("task_id")
    task_parser.add_argument("agent_id")
    task_parser.add_argument("--role", default="worker")
    task_parser.add_argument("--step")
    task_parser.add_argument("--summary")
    task_parser.add_argument("--instruction")
    task_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    task_parser.add_argument("--heartbeat-seconds", type=int, default=10)
    task_parser.add_argument("--provider-arg", action="append", dest="provider_args")

    conversation_parser = subparsers.add_parser("conversation")
    conversation_parser.add_argument("message")
    conversation_parser.add_argument("--title")
    conversation_parser.add_argument("--task-type", choices=["feature", "issue"], default="feature")
    conversation_parser.add_argument("--slug")
    conversation_parser.add_argument("--agent-id", default="worker-1")
    conversation_parser.add_argument("--role", default="worker")
    conversation_parser.add_argument("--instruction")
    conversation_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    conversation_parser.add_argument("--provider-arg", action="append", dest="provider_args")

    args, extras = parser.parse_known_args(normalized_argv)
    if args.launch_mode == "conversation":
        return _run_conversation_mode(
            provider=provider,
            repo_root=repo_root,
            config=config,
            message=args.message,
            title=args.title,
            task_type=args.task_type,
            slug=args.slug,
            agent_id=args.agent_id,
            role=args.role,
            instruction=args.instruction,
            owned_paths=args.owned_paths,
            provider_args=args.provider_args,
        )

    command = list(extras)
    launch: ProviderLaunch | None = None
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        launch = _build_default_launch(
            provider=provider,
            repo_root=repo_root,
            config=config,
            task_id=args.task_id,
            extra_instruction=args.instruction,
            provider_args=args.provider_args or [],
            owned_paths=args.owned_paths,
        )
        command = launch.command

    effective_provider = launch.effective_provider if launch else provider
    exit_code = handle_agent_run(
        task_id=args.task_id,
        agent_id=args.agent_id,
        role=args.role,
        provider=effective_provider,
        step=args.step or (launch.step if launch else None),
        summary=args.summary or (launch.summary if launch else None),
        owned_paths=args.owned_paths,
        heartbeat_seconds=args.heartbeat_seconds,
        command=command,
        stdin_text=launch.stdin_text if launch else None,
        env=launch.env if launch else None,
        repo_root=repo_root,
    )
    return _finalize_default_launch(
        repo_root=repo_root,
        config=config,
        task_id=args.task_id,
        agent_id=args.agent_id,
        provider=effective_provider,
        exit_code=exit_code,
        output_last_message_path=launch.output_last_message_path if launch else None,
        receipt_path=launch.receipt_path if launch else None,
        workdir=launch.workdir if launch else repo_root,
    )


def _run_conversation_mode(
    *,
    provider: str,
    repo_root: Path,
    config,
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    agent_id: str,
    role: str,
    instruction: str | None,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
) -> int:
    from .daemon import process_inbox_event, queue_conversation_event

    event, event_path = queue_conversation_event(
        repo_root,
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
        auto_run=True,
    )
    processed = process_inbox_event(repo_root=repo_root, config=config, event_path=event_path)
    if processed.get("status") != "processed":
        print(f"error: {processed.get('error') or 'conversation task launch failed'}", file=sys.stderr)
        return 1

    result = processed.get("result", {})
    print(f"created {result.get('task_id')}")
    print(f"branch: {result.get('branch')}")
    print(f"worktree_path: {result.get('worktree_path')}")
    if result.get("agent_id"):
        print(f"agent_id: {result.get('agent_id')}")
    return 0


def _build_default_launch(
    *,
    provider: str,
    repo_root: Path,
    config,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
    owned_paths: list[str] | None,
) -> ProviderLaunch:
    if provider == "codex":
        return _build_codex_launch(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=extra_instruction,
            provider_args=provider_args,
        )
    if is_local_openai_provider(provider):
        return _build_local_launch(
            provider=provider,
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=extra_instruction,
            provider_args=provider_args,
            owned_paths=owned_paths,
        )
    raise RuntimeError(f"default launch is not configured for provider: {provider}")


def _build_codex_launch(
    *,
    repo_root: Path,
    config,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
) -> ProviderLaunch:
    codex = _resolve_codex_executable()
    prompt = build_codex_prompt(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        extra_instruction=extra_instruction,
    )
    env = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": str(prompt.workdir),
    }
    output_path = _allocate_temp_path(task_id, ".last.txt")
    command = [
        codex,
        "exec",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "--output-last-message",
        str(output_path),
        "-C",
        str(prompt.workdir),
        *provider_args,
        "-",
    ]
    return ProviderLaunch(
        command=command,
        stdin_text=prompt.prompt,
        step=f"running codex task {task_id}",
        summary=f"codex exec started for {task_id}",
        env=env,
        output_last_message_path=output_path,
        effective_provider="codex",
        workdir=prompt.workdir,
    )


def _build_local_launch(
    *,
    provider: str,
    repo_root: Path,
    config,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
    owned_paths: list[str] | None,
) -> ProviderLaunch:
    try:
        local_config = parse_local_provider_args(provider, provider_args)
    except LocalProviderConfigError as exc:
        raise RuntimeError(str(exc)) from exc
    if local_config.fallback_provider and not local_provider_available(local_config):
        label = "Gemma" if local_config.provider == "gemma" else local_config.provider
        fallback_note = f"{label} local provider was unavailable; falling back to {local_config.fallback_provider}."
        combined_instruction = fallback_note if not extra_instruction else f"{fallback_note}\n{extra_instruction}"
        return _build_default_launch(
            provider=local_config.fallback_provider,
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=combined_instruction,
            provider_args=[],
            owned_paths=owned_paths,
        )

    label = "Gemma" if local_config.provider == "gemma" else local_config.provider
    prompt = build_local_worker_prompt(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        extra_instruction=extra_instruction,
        worker_name=label,
    )
    effective_owned_paths = tuple(owned_paths or prompt.owned_paths)
    output_path = _allocate_temp_path(task_id, ".last.txt")
    receipt_path = _allocate_temp_path(task_id, ".local-agent.json")
    command = build_local_worker_command(
        local_config,
        workspace=prompt.workdir,
        output_last_message_path=output_path,
        receipt_path=receipt_path,
        owned_paths=effective_owned_paths,
        observation_hash=prompt.observation_hash,
    )
    return ProviderLaunch(
        command=command,
        stdin_text=prompt.prompt,
        step=f"running {local_config.provider} task {task_id}",
        summary=f"{local_config.provider} bounded local agent started for {task_id}",
        env=_local_worker_env(local_config),
        output_last_message_path=output_path,
        effective_provider=local_config.provider,
        workdir=prompt.workdir,
        receipt_path=receipt_path,
    )


def _resolve_codex_executable() -> str:
    for candidate in ("codex.cmd", "codex"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("could not find local codex executable")


def _normalize_wrapper_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] in {"task", "conversation"}:
        return list(argv)
    return ["task", *argv]


def _allocate_temp_path(task_id: str, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(prefix=f"sisyphus-{task_id}-", suffix=suffix, delete=False) as handle:
        return Path(handle.name)


def _local_worker_env(config: LocalProviderConfig) -> dict[str, str]:
    src_root = Path(__file__).resolve().parents[1]
    existing = os.environ.get("PYTHONPATH")
    env = {"PYTHONPATH": str(src_root) if not existing else f"{src_root}{os.pathsep}{existing}"}
    if config.api_key:
        env["SISYPHUS_LOCAL_MODEL_API_KEY"] = config.api_key
    return env


def _finalize_default_launch(
    *,
    repo_root: Path,
    config,
    task_id: str,
    agent_id: str,
    provider: str,
    exit_code: int,
    output_last_message_path: Path | None,
    receipt_path: Path | None = None,
    workdir: Path | None = None,
) -> int:
    if output_last_message_path is None:
        return exit_code
    receipt = _read_receipt(receipt_path)
    try:
        last_message = _read_last_message(output_last_message_path)
        if receipt is not None:
            _persist_local_receipt(repo_root, config, task_id, agent_id, receipt)
    finally:
        output_last_message_path.unlink(missing_ok=True)
        if receipt_path is not None:
            receipt_path.unlink(missing_ok=True)

    if exit_code != 0:
        if is_local_openai_provider(provider) and receipt is not None:
            _mark_agent_failed(
                repo_root=repo_root,
                config=config,
                task_id=task_id,
                agent_id=agent_id,
                provider=provider,
                error=str(receipt.get("error") or receipt.get("summary") or "local agent failed"),
                last_message=last_message,
            )
        return exit_code

    final_status = _classify_last_message(last_message)
    if is_local_openai_provider(provider) and final_status is None:
        error = "local agent did not report a structured final status"
        _mark_agent_failed(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            provider=provider,
            error=error,
            last_message=last_message,
        )
        return 1
    if final_status == "completed":
        if is_local_openai_provider(provider):
            completion_error = _local_completion_error(receipt, workdir or repo_root)
            if completion_error:
                _mark_agent_failed(
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
        _mark_agent_failed(
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


def _read_last_message(output_last_message_path: Path) -> str | None:
    if not output_last_message_path.exists():
        return None
    content = output_last_message_path.read_text(encoding="utf-8", errors="replace").strip()
    return content or None


def _read_receipt(receipt_path: Path | None) -> dict[str, object] | None:
    if receipt_path is None or not receipt_path.exists():
        return None
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _local_completion_error(receipt: dict[str, object] | None, workdir: Path) -> str | None:
    if receipt is None:
        return "unsupported completion claim: local agent receipt is missing or invalid"
    if receipt.get("schema_version") != "sisyphus.local_agent_run.v1" or receipt.get("status") != "completed":
        return "unsupported completion claim: local agent receipt does not report a completed run"
    facts = receipt.get("completion_facts")
    if not isinstance(facts, dict) or facts.get("completion_ready") is not True:
        return "unsupported completion claim: receipt lacks code-and-test completion evidence"
    actual_changes = _non_planning_changed_files(workdir)
    if not actual_changes:
        return "unsupported completion claim: no code-level result exists outside .planning"
    mutation_step = facts.get("last_mutation_step")
    test_step = facts.get("last_successful_test_step")
    baseline_step = facts.get("baseline_test_step")
    if type(baseline_step) is not int or type(mutation_step) is not int or baseline_step >= mutation_step:
        return "unsupported completion claim: no baseline test was recorded before mutation"
    if type(test_step) is not int or test_step <= mutation_step:
        return "unsupported completion claim: no passing test was recorded after the latest mutation"
    receipt_changes = facts.get("changed_files")
    if not isinstance(receipt_changes, list) or not {
        str(path) for path in receipt_changes if isinstance(path, str)
    }.intersection(actual_changes):
        return "unsupported completion claim: receipt changed files do not match the worktree diff"
    return None


def _non_planning_changed_files(workdir: Path) -> set[str]:
    commands = (
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                text=True,
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
        if completed.returncode != 0:
            return set()
        paths.update(line.strip() for line in completed.stdout.splitlines() if line.strip())
    return {
        path
        for path in paths
        if ".planning" not in Path(path).parts and ".git" not in Path(path).parts
    }


def _persist_local_receipt(
    repo_root: Path,
    config,
    task_id: str,
    agent_id: str,
    receipt: dict[str, object],
) -> None:
    try:
        from .state import load_task_record

        task, task_file = load_task_record(
            repo_root=repo_root,
            task_dir_name=config.task_dir,
            task_id=task_id,
        )
        path = task_file.parent / "artifacts" / "local-agent" / f"{agent_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _append_local_episode_steps(task, task_file.parent, agent_id, receipt)
    except (OSError, UnicodeError, FileNotFoundError):
        return


def _append_local_episode_steps(
    task: dict,
    task_dir: Path,
    agent_id: str,
    receipt: dict[str, object],
) -> None:
    from .episode_trace import (
        append_episode_step,
        build_episode_step,
        default_episode_id,
        next_episode_step,
    )
    from .observation import build_task_observation

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


def _mark_agent_failed(
    *,
    repo_root: Path,
    config,
    task_id: str,
    agent_id: str,
    provider: str,
    error: str,
    last_message: str | None,
) -> None:
    try:
        update_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            status="failed",
            provider=provider,
            error=error,
            last_message_summary=last_message or error,
        )
    except (AgentTrackingError, FileNotFoundError):
        pass


def _classify_last_message(last_message: str | None) -> str | None:
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


__all__ = ["ProviderLaunch", "run_provider_wrapper"]
