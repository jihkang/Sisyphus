from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error, request

from .local_agent import LocalCodingAgent
from ..infra.workspace import WorkspaceExecutor


DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"
DEFAULT_GEMMA_MODEL = "gemma-12b"
DEFAULT_TEST_COMMAND = "python3 -m unittest discover -s tests"
LOCAL_OPENAI_PROVIDERS = {"gemma", "local-openai", "llama-server"}
MAX_MODEL_RESPONSE_BYTES = 1_000_000


class LocalProviderConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocalProviderConfig:
    provider: str = "local-openai"
    base_url: str = DEFAULT_BASE_URL
    model: str = "local-model"
    timeout_seconds: float = 120.0
    temperature: float = 0.1
    max_tokens: int = 1024
    api_key: str | None = None
    fallback_provider: str | None = "codex"
    availability_timeout_seconds: float = 0.5
    max_steps: int = 24
    max_protocol_errors: int = 3
    context_window_tokens: int = 8192
    context_reserve_tokens: int = 1024
    compact_ratio: float = 0.75
    max_tool_output_chars: int = 8000
    command_timeout_seconds: float = 120.0
    test_commands: tuple[str, ...] = (DEFAULT_TEST_COMMAND,)


class OpenAICompatibleClient:
    def __init__(self, config: LocalProviderConfig) -> None:
        self.config = config

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        http_request = request.Request(
            f"{self.config.base_url}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                response_bytes = response.read(MAX_MODEL_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            detail = exc.read(self.config.max_tool_output_chars + 1).decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(f"local provider request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise RuntimeError(
                f"local provider request failed for {self.config.base_url}; "
                "start an OpenAI-compatible local server or configure a fallback"
            ) from exc
        if len(response_bytes) > MAX_MODEL_RESPONSE_BYTES:
            raise RuntimeError(
                f"local provider response exceeds {MAX_MODEL_RESPONSE_BYTES} bytes"
            )
        response_body = response_bytes.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("local provider returned invalid JSON") from exc
        content = _extract_message_content(parsed)
        if not content.strip():
            raise RuntimeError("local provider returned an empty assistant message")
        return content.strip()


def is_local_openai_provider(provider: str) -> bool:
    return provider.strip().lower() in LOCAL_OPENAI_PROVIDERS


def parse_local_provider_args(
    provider: str,
    provider_args: list[str] | None,
    *,
    env: dict[str, str] | None = None,
) -> LocalProviderConfig:
    environment = os.environ if env is None else env
    parser = argparse.ArgumentParser(
        prog=f"{provider}-local-provider",
        add_help=False,
        exit_on_error=False,
    )
    _add_config_arguments(parser)
    try:
        args, unknown = parser.parse_known_args(provider_args or [])
    except argparse.ArgumentError as exc:
        raise LocalProviderConfigError(str(exc)) from exc
    if unknown:
        raise LocalProviderConfigError(f"unsupported local provider argument(s): {' '.join(unknown)}")

    normalized_provider = provider.strip().lower()
    base_url = _first_non_empty(
        args.base_url,
        environment.get("SISYPHUS_GEMMA_BASE_URL") if normalized_provider == "gemma" else None,
        environment.get("SISYPHUS_LOCAL_MODEL_BASE_URL"),
        DEFAULT_BASE_URL,
    )
    model = _first_non_empty(
        args.model,
        environment.get("SISYPHUS_GEMMA_MODEL") if normalized_provider == "gemma" else None,
        environment.get("SISYPHUS_LOCAL_MODEL_NAME"),
        DEFAULT_GEMMA_MODEL if normalized_provider == "gemma" else "local-model",
    )
    api_key = _first_non_empty(
        args.api_key,
        environment.get("SISYPHUS_LOCAL_MODEL_API_KEY"),
        environment.get("OPENAI_API_KEY"),
        default=None,
    )
    fallback_provider = _fallback_provider(args, environment, normalized_provider)
    availability_timeout = _environment_float(
        args.availability_timeout,
        environment.get("SISYPHUS_LOCAL_MODEL_AVAILABILITY_TIMEOUT"),
        default=0.5,
        label="local provider availability timeout",
    )
    test_commands = tuple(args.test_command or [DEFAULT_TEST_COMMAND])

    config = LocalProviderConfig(
        provider=normalized_provider,
        base_url=str(base_url).rstrip("/"),
        model=str(model),
        timeout_seconds=float(args.timeout if args.timeout is not None else 120.0),
        temperature=float(args.temperature),
        max_tokens=int(args.max_tokens),
        api_key=str(api_key) if api_key else None,
        fallback_provider=fallback_provider,
        availability_timeout_seconds=availability_timeout,
        max_steps=int(args.max_steps),
        max_protocol_errors=int(args.max_protocol_errors),
        context_window_tokens=int(args.context_window),
        context_reserve_tokens=int(args.context_reserve),
        compact_ratio=float(args.compact_ratio),
        max_tool_output_chars=int(args.max_tool_output_chars),
        command_timeout_seconds=float(args.command_timeout),
        test_commands=test_commands,
    )
    _validate_config(config)
    return config


def local_provider_available(config: LocalProviderConfig) -> bool:
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    try:
        http_request = request.Request(f"{config.base_url}/models", headers=headers, method="GET")
        with request.urlopen(http_request, timeout=config.availability_timeout_seconds) as response:
            response.read(1)
        return True
    except (OSError, error.HTTPError):
        return False


def build_worker_command(
    config: LocalProviderConfig,
    *,
    workspace: Path,
    output_last_message_path: Path,
    receipt_path: Path,
    owned_paths: tuple[str, ...],
    observation_hash: str | None,
) -> list[str]:
    command = [
        sys.executable,
        "-c",
        "from sisyphus.providers.local_openai import main; raise SystemExit(main())",
        "--provider",
        config.provider,
        "--base-url",
        config.base_url,
        "--model",
        config.model,
        "--timeout",
        str(config.timeout_seconds),
        "--temperature",
        str(config.temperature),
        "--max-tokens",
        str(config.max_tokens),
        "--max-steps",
        str(config.max_steps),
        "--max-protocol-errors",
        str(config.max_protocol_errors),
        "--context-window",
        str(config.context_window_tokens),
        "--context-reserve",
        str(config.context_reserve_tokens),
        "--compact-ratio",
        str(config.compact_ratio),
        "--max-tool-output-chars",
        str(config.max_tool_output_chars),
        "--command-timeout",
        str(config.command_timeout_seconds),
        "--workspace",
        str(workspace),
        "--output-last-message",
        str(output_last_message_path),
        "--receipt",
        str(receipt_path),
        "--no-fallback",
    ]
    if observation_hash:
        command.extend(["--observation-hash", observation_hash])
    for owned_path in owned_paths:
        command.extend(["--owned-path", owned_path])
    for test_command in config.test_commands:
        command.extend(["--test-command", test_command])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sisyphus-local-openai-provider")
    parser.add_argument("--provider", default="local-openai")
    _add_config_arguments(parser)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--owned-path", action="append", default=[])
    parser.add_argument("--observation-hash")
    parser.add_argument("--output-last-message", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)

    config_args = _config_argv_from_namespace(args)
    try:
        config = parse_local_provider_args(args.provider, config_args)
        executor = WorkspaceExecutor(
            Path(args.workspace),
            owned_paths=tuple(args.owned_path),
            test_commands=config.test_commands,
            command_timeout_seconds=config.command_timeout_seconds,
            max_output_chars=config.max_tool_output_chars,
        )
    except (LocalProviderConfigError, ValueError) as exc:
        message = f"STATUS: failed\n{exc}\n"
        Path(args.output_last_message).write_text(message, encoding="utf-8")
        print(message, end="")
        return 1

    agent = LocalCodingAgent(
        config=config,
        client=OpenAICompatibleClient(config),
        executor=executor,
        receipt_path=Path(args.receipt),
        observation_hash=args.observation_hash,
    )
    result = agent.run(sys.stdin.read())
    message = result.final_message()
    Path(args.output_last_message).write_text(message, encoding="utf-8")
    print(message, end="")
    return 0 if result.status == "completed" else 1


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--timeout", "--timeout-seconds", type=float)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--api-key")
    parser.add_argument("--fallback-provider")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--availability-timeout", type=float)
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--max-protocol-errors", type=int, default=3)
    parser.add_argument("--context-window", type=int, default=8192)
    parser.add_argument("--context-reserve", type=int, default=1024)
    parser.add_argument("--compact-ratio", type=float, default=0.75)
    parser.add_argument("--max-tool-output-chars", type=int, default=8000)
    parser.add_argument("--command-timeout", type=float, default=120.0)
    parser.add_argument("--test-command", action="append")


def _config_argv_from_namespace(args: argparse.Namespace) -> list[str]:
    values = [
        "--base-url", str(args.base_url or DEFAULT_BASE_URL),
        "--model", str(args.model or "local-model"),
        "--timeout", str(args.timeout if args.timeout is not None else 120.0),
        "--temperature", str(args.temperature),
        "--max-tokens", str(args.max_tokens),
        "--max-steps", str(args.max_steps),
        "--max-protocol-errors", str(args.max_protocol_errors),
        "--context-window", str(args.context_window),
        "--context-reserve", str(args.context_reserve),
        "--compact-ratio", str(args.compact_ratio),
        "--max-tool-output-chars", str(args.max_tool_output_chars),
        "--command-timeout", str(args.command_timeout),
    ]
    if args.api_key:
        values.extend(["--api-key", args.api_key])
    if args.no_fallback:
        values.append("--no-fallback")
    elif args.fallback_provider:
        values.extend(["--fallback-provider", args.fallback_provider])
    if args.availability_timeout is not None:
        values.extend(["--availability-timeout", str(args.availability_timeout)])
    for command in args.test_command or []:
        values.extend(["--test-command", command])
    return values


def _validate_config(config: LocalProviderConfig) -> None:
    if not config.base_url:
        raise LocalProviderConfigError("local provider base URL is required")
    if not config.model:
        raise LocalProviderConfigError("local provider model is required")
    if config.timeout_seconds <= 0 or config.availability_timeout_seconds <= 0:
        raise LocalProviderConfigError("local provider timeouts must be positive")
    if not 0 <= config.temperature <= 2:
        raise LocalProviderConfigError("local provider temperature must be between 0 and 2")
    if config.max_tokens < 1:
        raise LocalProviderConfigError("local provider max tokens must be positive")
    if config.max_steps < 1:
        raise LocalProviderConfigError("local provider max steps must be positive")
    if config.max_protocol_errors < 0:
        raise LocalProviderConfigError("local provider protocol error budget cannot be negative")
    if config.context_reserve_tokens >= config.context_window_tokens:
        raise LocalProviderConfigError("local provider context reserve must be smaller than the context window")
    if not 0.1 <= config.compact_ratio <= 0.95:
        raise LocalProviderConfigError("local provider compact ratio must be between 0.1 and 0.95")
    if config.max_tool_output_chars < 256:
        raise LocalProviderConfigError("local provider tool output limit must be at least 256")
    if config.command_timeout_seconds <= 0:
        raise LocalProviderConfigError("local provider command timeout must be positive")
    if not config.test_commands:
        raise LocalProviderConfigError("local provider requires at least one operator-configured test command")


def _fallback_provider(args: argparse.Namespace, env: dict[str, str], provider: str) -> str | None:
    if args.no_fallback:
        return None
    raw = args.fallback_provider
    if raw is None:
        raw = env.get("SISYPHUS_LOCAL_MODEL_FALLBACK_PROVIDER", "codex")
    fallback = str(raw).strip().lower()
    if fallback in {"", "none", "disabled", "off", "false"}:
        return None
    if fallback == provider:
        raise LocalProviderConfigError("local provider fallback cannot point to the same provider")
    return fallback


def _environment_float(
    explicit: float | None,
    environment_value: str | None,
    *,
    default: float,
    label: str,
) -> float:
    if explicit is not None:
        return float(explicit)
    if environment_value is None:
        return default
    try:
        return float(environment_value)
    except ValueError as exc:
        raise LocalProviderConfigError(f"{label} must be numeric") from exc


def _first_non_empty(*values: str | None, default: str | None = "") -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _extract_message_content(parsed: object) -> str:
    if not isinstance(parsed, dict):
        return ""
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return str(message["content"])
    return str(first.get("text")) if isinstance(first.get("text"), str) else ""


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_GEMMA_MODEL",
    "DEFAULT_TEST_COMMAND",
    "LOCAL_OPENAI_PROVIDERS",
    "MAX_MODEL_RESPONSE_BYTES",
    "LocalProviderConfig",
    "LocalProviderConfigError",
    "OpenAICompatibleClient",
    "build_worker_command",
    "is_local_openai_provider",
    "local_provider_available",
    "main",
    "parse_local_provider_args",
]
