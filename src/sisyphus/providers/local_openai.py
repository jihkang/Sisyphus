from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib import error, request

from .local_agent import LocalCodingAgent
from ..infra.providers.local_config import (
    DEFAULT_BASE_URL,
    DEFAULT_GEMMA_MODEL,
    DEFAULT_TEST_COMMAND,
    LOCAL_OPENAI_PROVIDERS,
    LocalProviderConfig,
    LocalProviderConfigError,
    add_local_provider_arguments as _add_config_arguments,
    build_worker_command,
    config_argv_from_namespace as _config_argv_from_namespace,
    is_local_openai_provider,
    local_provider_available,
    parse_local_provider_args,
)
from ..infra.workspace import WorkspaceExecutor


MAX_MODEL_RESPONSE_BYTES = 1_000_000


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sisyphus-local-openai-provider")
    parser.add_argument("--provider", default="local-openai")
    _add_config_arguments(parser)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--owned-path", action="append", default=[])
    parser.add_argument("--observation-hash")
    parser.add_argument("--request-digest")
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
        request_digest=args.request_digest,
    )
    result = agent.run(sys.stdin.read())
    message = result.final_message()
    Path(args.output_last_message).write_text(message, encoding="utf-8")
    print(message, end="")
    return 0 if result.status == "completed" else 1


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
