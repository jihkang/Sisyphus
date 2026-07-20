from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Protocol

from ...shared.digests import stable_json_hash
from .local_config import (
    LocalProviderConfig,
    LocalProviderConfigError,
    build_worker_command as build_local_worker_command,
    is_local_openai_provider,
    local_provider_available,
    parse_local_provider_args,
)


class ProviderPrompt(Protocol):
    workdir: Path
    prompt: str
    owned_paths: tuple[str, ...]
    observation_hash: str | None


PromptBuilder = Callable[..., ProviderPrompt]


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
    request_digest: str | None = None


def build_default_launch(
    *,
    provider: str,
    repo_root: Path,
    config: object,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
    owned_paths: list[str] | None,
    codex_prompt_builder: PromptBuilder,
    local_prompt_builder: PromptBuilder,
    resolve_codex_executable: Callable[[], str] | None = None,
    provider_available: Callable[[LocalProviderConfig], bool] | None = None,
) -> ProviderLaunch:
    executable_resolver = resolve_codex_executable or find_codex_executable
    availability_check = provider_available or local_provider_available
    if provider == "codex":
        return build_codex_launch(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=extra_instruction,
            provider_args=provider_args,
            prompt_builder=codex_prompt_builder,
            resolve_codex_executable=executable_resolver,
        )
    if is_local_openai_provider(provider):
        return build_local_launch(
            provider=provider,
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=extra_instruction,
            provider_args=provider_args,
            owned_paths=owned_paths,
            codex_prompt_builder=codex_prompt_builder,
            local_prompt_builder=local_prompt_builder,
            resolve_codex_executable=executable_resolver,
            provider_available=availability_check,
        )
    raise RuntimeError(f"default launch is not configured for provider: {provider}")


def build_codex_launch(
    *,
    repo_root: Path,
    config: object,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
    prompt_builder: PromptBuilder,
    resolve_codex_executable: Callable[[], str] | None = None,
) -> ProviderLaunch:
    resolver = resolve_codex_executable or find_codex_executable
    prompt = prompt_builder(
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
    output_path = allocate_temp_path(task_id, ".last.txt")
    command = [
        resolver(),
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


def build_local_launch(
    *,
    provider: str,
    repo_root: Path,
    config: object,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
    owned_paths: list[str] | None,
    codex_prompt_builder: PromptBuilder,
    local_prompt_builder: PromptBuilder,
    resolve_codex_executable: Callable[[], str] | None = None,
    provider_available: Callable[[LocalProviderConfig], bool] | None = None,
) -> ProviderLaunch:
    try:
        local_config = parse_local_provider_args(provider, provider_args)
    except LocalProviderConfigError as exc:
        raise RuntimeError(str(exc)) from exc
    availability_check = provider_available or local_provider_available
    if local_config.fallback_provider and not availability_check(local_config):
        label = "Gemma" if local_config.provider == "gemma" else local_config.provider
        fallback_note = (
            f"{label} local provider was unavailable; "
            f"falling back to {local_config.fallback_provider}."
        )
        combined_instruction = (
            fallback_note if not extra_instruction else f"{fallback_note}\n{extra_instruction}"
        )
        return build_default_launch(
            provider=local_config.fallback_provider,
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            extra_instruction=combined_instruction,
            provider_args=[],
            owned_paths=owned_paths,
            codex_prompt_builder=codex_prompt_builder,
            local_prompt_builder=local_prompt_builder,
            resolve_codex_executable=resolve_codex_executable,
            provider_available=availability_check,
        )

    label = "Gemma" if local_config.provider == "gemma" else local_config.provider
    prompt = local_prompt_builder(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        extra_instruction=extra_instruction,
        worker_name=label,
    )
    effective_owned_paths = tuple(owned_paths or prompt.owned_paths)
    request_digest = stable_json_hash(
        {
            "task_id": task_id,
            "provider": local_config.provider,
            "base_url": local_config.base_url,
            "model": local_config.model,
            "timeout_seconds": local_config.timeout_seconds,
            "temperature": local_config.temperature,
            "max_tokens": local_config.max_tokens,
            "max_steps": local_config.max_steps,
            "max_protocol_errors": local_config.max_protocol_errors,
            "context_window_tokens": local_config.context_window_tokens,
            "context_reserve_tokens": local_config.context_reserve_tokens,
            "compact_ratio": local_config.compact_ratio,
            "max_tool_output_chars": local_config.max_tool_output_chars,
            "command_timeout_seconds": local_config.command_timeout_seconds,
            "test_commands": local_config.test_commands,
            "workdir": str(prompt.workdir.resolve()),
            "owned_paths": effective_owned_paths,
            "observation_hash": prompt.observation_hash,
            "prompt_digest": stable_json_hash({"prompt": prompt.prompt}),
        }
    )
    output_path = allocate_temp_path(task_id, ".last.txt")
    receipt_path = allocate_temp_path(task_id, ".local-agent.json")
    command = build_local_worker_command(
        local_config,
        workspace=prompt.workdir,
        output_last_message_path=output_path,
        receipt_path=receipt_path,
        owned_paths=effective_owned_paths,
        observation_hash=prompt.observation_hash,
        request_digest=request_digest,
    )
    return ProviderLaunch(
        command=command,
        stdin_text=prompt.prompt,
        step=f"running {local_config.provider} task {task_id}",
        summary=f"{local_config.provider} bounded local agent started for {task_id}",
        env=local_worker_env(local_config),
        output_last_message_path=output_path,
        effective_provider=local_config.provider,
        workdir=prompt.workdir,
        receipt_path=receipt_path,
        request_digest=request_digest,
    )


def find_codex_executable() -> str:
    for candidate in ("codex.cmd", "codex"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("could not find local codex executable")


def allocate_temp_path(task_id: str, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix=f"sisyphus-{task_id}-",
        suffix=suffix,
        delete=False,
    ) as handle:
        return Path(handle.name)


def local_worker_env(config: LocalProviderConfig) -> dict[str, str]:
    src_root = Path(__file__).resolve().parents[3]
    existing = os.environ.get("PYTHONPATH")
    env = {
        "PYTHONPATH": str(src_root)
        if not existing
        else f"{src_root}{os.pathsep}{existing}"
    }
    if config.api_key:
        env["SISYPHUS_LOCAL_MODEL_API_KEY"] = config.api_key
    return env


__all__ = [
    "ProviderLaunch",
    "allocate_temp_path",
    "build_codex_launch",
    "build_default_launch",
    "build_local_launch",
    "find_codex_executable",
    "local_worker_env",
]
