from __future__ import annotations

import inspect
from pathlib import Path
import sys

from .agents import AgentTrackingError, update_agent
from .application.commands.agent import RunTrackedAgentCommand
from .application.use_cases.agent_launch import AgentLaunchError
from .composition.agent_launch import build_agent_launch_service
from .composition.daemon import build_repository_inbox_processing_service
from .composition.inbox import build_inbox_queue_service
from .composition.provider_receipts import persist_local_provider_receipt
from .config import load_config
from .codex_prompt import build_codex_prompt, build_local_worker_prompt
from .discovery import detect_repo_root
from .infra.providers.conversation import run_legacy_conversation
from .infra.daemon import new_event_id
from .infra.providers.launch import (
    ProviderLaunch,
    build_default_launch,
    find_codex_executable,
)
from .infra.providers.receipts import finalize_default_launch
from .interfaces.provider_wrapper import (
    ConversationLaunchRequest,
    parse_provider_wrapper_request,
)
from .infra.providers.local_config import local_provider_available


def run_provider_wrapper(provider: str, argv: list[str], *, repo_root: Path | None = None) -> int:
    repo_root = repo_root or detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    request = parse_provider_wrapper_request(provider, argv)
    if isinstance(request, ConversationLaunchRequest):
        return _run_conversation_mode(
            provider=provider,
            repo_root=repo_root,
            config=config,
            message=request.message,
            title=request.title,
            task_type=request.task_type,
            slug=request.slug,
            agent_id=request.agent_id,
            role=request.role,
            instruction=request.instruction,
            owned_paths=list(request.owned_paths) or None,
            provider_args=list(request.provider_args) or None,
        )

    command = list(request.command)
    launch: ProviderLaunch | None = None
    if not command:
        launch = _build_default_launch(
            provider=provider,
            repo_root=repo_root,
            config=config,
            task_id=request.task_id,
            extra_instruction=request.instruction,
            provider_args=list(request.provider_args),
            owned_paths=list(request.owned_paths) or None,
        )
        command = launch.command

    effective_provider = launch.effective_provider if launch else provider
    exit_code = _agent_runner_override()(
        task_id=request.task_id,
        agent_id=request.agent_id,
        role=request.role,
        provider=effective_provider,
        step=request.step or (launch.step if launch else None),
        summary=request.summary or (launch.summary if launch else None),
        owned_paths=list(request.owned_paths) or None,
        heartbeat_seconds=request.heartbeat_seconds,
        command=command,
        stdin_text=launch.stdin_text if launch else None,
        env=launch.env if launch else None,
        repo_root=repo_root,
    )
    return _finalize_default_launch(
        repo_root=repo_root,
        config=config,
        task_id=request.task_id,
        agent_id=request.agent_id,
        provider=effective_provider,
        exit_code=exit_code,
        output_last_message_path=launch.output_last_message_path if launch else None,
        receipt_path=launch.receipt_path if launch else None,
        workdir=launch.workdir if launch else repo_root,
        expected_request_digest=launch.request_digest if launch else None,
    )


def _agent_runner_override():
    """Honor an explicit public CLI override without depending on CLI in normal execution."""
    for module_name in ("sisyphus.cli", "sisyphus.interfaces.cli.app"):
        module = sys.modules.get(module_name)
        candidate = getattr(module, "handle_agent_run", None) if module is not None else None
        if candidate is None:
            continue
        if not (
            inspect.isfunction(candidate)
            and candidate.__module__ == "sisyphus.interfaces.cli.app"
            and candidate.__name__ == "handle_agent_run"
        ):
            return candidate
    return _run_agent_application


def _run_agent_application(
    *,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    heartbeat_seconds: int,
    command: list[str],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    repo_root: str | Path | None = None,
) -> int:
    resolved_root = detect_repo_root(Path(repo_root).resolve()) if repo_root else detect_repo_root(Path.cwd())
    config = load_config(resolved_root)
    try:
        outcome = build_agent_launch_service(resolved_root, config).run(
            RunTrackedAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                role=role,
                provider=provider,
                command=tuple(command),
                current_step=step,
                last_message_summary=summary,
                owned_paths=tuple(owned_paths or ()),
                heartbeat_seconds=heartbeat_seconds,
                run_cwd=str(resolved_root),
                stdin_text=stdin_text,
                env=tuple((env or {}).items()),
            )
        )
    except (AgentLaunchError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"agent {outcome.agent_id}")
    print(f"task: {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"exit_code: {outcome.exit_code}")
    return outcome.exit_code


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
    return run_legacy_conversation(
        provider=provider,
        repo_root=repo_root,
        config=config,
        queue=build_inbox_queue_service(
            repo_root,
            config,
            new_event_id=new_event_id,
        ),
        processor=build_repository_inbox_processing_service(repo_root, config),
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        owned_paths=owned_paths,
        provider_args=provider_args,
    )


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
    return build_default_launch(
        provider=provider,
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        extra_instruction=extra_instruction,
        provider_args=provider_args,
        owned_paths=owned_paths,
        codex_prompt_builder=build_codex_prompt,
        local_prompt_builder=build_local_worker_prompt,
        resolve_codex_executable=_resolve_codex_executable,
        provider_available=local_provider_available,
    )


def _resolve_codex_executable() -> str:
    return find_codex_executable()


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
    expected_request_digest: str | None = None,
) -> int:
    return finalize_default_launch(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        provider=provider,
        exit_code=exit_code,
        output_last_message_path=output_last_message_path,
        receipt_path=receipt_path,
        workdir=workdir,
        expected_request_digest=expected_request_digest,
        mark_agent_failed=_mark_agent_failed,
        persist_receipt=persist_local_provider_receipt,
    )


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
__all__ = ["ProviderLaunch", "run_provider_wrapper"]
