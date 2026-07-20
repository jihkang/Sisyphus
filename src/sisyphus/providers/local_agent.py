from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Protocol

from ..application.ports.workspace import SUPPORTED_WORKSPACE_ACTIONS, WorkspacePort
from ..compat.serialization import install_serialization_compat
from ..shared.clock import utc_now
from .codecs import encode_local_agent_run_result
from ..infra.providers.receipt_schema import sign_local_agent_receipt
from ..infra.persistence.json_store import write_json_file


LOCAL_AGENT_SCHEMA_VERSION = "sisyphus.local_agent_run.v1"
LOCAL_AGENT_ACTIONS = (*SUPPORTED_WORKSPACE_ACTIONS, "finish")

SYSTEM_PROMPT = """You are a bounded local coding policy inside Sisyphus.
Return exactly one JSON object per turn and no prose.
Available actions:
- {"action":"list_files","path":"optional/relative/path"}
- {"action":"read_file","path":"relative/path","start_line":1,"end_line":400}
- {"action":"search","query":"literal text","path":"optional/relative/path"}
- {"action":"write_file","path":"owned/relative/path","content":"complete UTF-8 file content"}
- {"action":"apply_patch","patch":"unified git diff"}
- {"action":"git_diff"}
- {"action":"run_test","command_id":0}
- {"action":"finish","status":"completed|blocked|failed","summary":"concise result"}
Never invent shell commands. Tests are selected only by command_id.
Use repository evidence before editing. A completed result requires a real non-planning change and a passing test after the latest edit.
After inspecting relevant code and tests, run one configured baseline test before the first mutation. A failing baseline is expected for a bug fix.
After a successful mutation, run a configured test instead of repeating the same write.
Do not request plan approval, spec freeze, close, promotion, or any other lifecycle action."""


class ChatCompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass(frozen=True, slots=True)
class LocalAgentRunResult:
    status: str
    summary: str
    error: str | None
    observation_hash: str | None
    request_digest: str | None
    started_at: str
    finished_at: str
    action_count: int
    protocol_error_count: int
    blocked_action_count: int
    compaction_count: int
    completion_facts: dict[str, object]
    events: tuple[dict[str, object], ...]
    schema_version: str = LOCAL_AGENT_SCHEMA_VERSION

    def final_message(self) -> str:
        return f"STATUS: {self.status}\n{self.summary}\n"


install_serialization_compat(
    LocalAgentRunResult,
    encode_mapping=encode_local_agent_run_result,
)


class LocalCodingAgent:
    def __init__(
        self,
        *,
        config,
        client: ChatCompletionClient,
        executor: WorkspacePort,
        receipt_path: Path | None = None,
        observation_hash: str | None = None,
        request_digest: str | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.executor = executor
        self.receipt_path = receipt_path
        self.observation_hash = observation_hash
        self.request_digest = request_digest
        self._events: list[dict[str, object]] = []
        self._compaction_count = 0
        self._last_compacted_event_count = 0

    def run(self, task_prompt: str) -> LocalAgentRunResult:
        started_at = utc_now()
        base_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_prompt.strip()},
        ]
        history: list[dict[str, str]] = []
        action_count = 0
        protocol_error_count = 0
        status = "failed"
        summary = "local agent exhausted its action budget"
        error: str | None = summary
        selection_phase_recorded = False

        for step in range(1, self.config.max_steps + 1):
            history = self._compact_history_if_needed(base_messages, history)
            messages = [*base_messages, *history]
            try:
                raw_response = self.client.complete(messages)
            except Exception as exc:
                summary = f"local provider request failed: {exc}"
                error = summary
                self._events.append(
                    {
                        "step": step,
                        "action": "provider_error",
                        "ok": False,
                        "error": str(exc),
                    }
                )
                break

            try:
                action = parse_model_action(raw_response)
            except ValueError as exc:
                protocol_error_count += 1
                event = {
                    "step": step,
                    "action": "protocol_error",
                    "ok": False,
                    "error": str(exc),
                }
                self._events.append(event)
                history.extend(
                    [
                        {"role": "assistant", "content": _bounded(raw_response, self.config.max_tool_output_chars)},
                        {
                            "role": "user",
                            "content": "TOOL_RESULT\n" + json.dumps(event, separators=(",", ":")),
                        },
                    ]
                )
                if protocol_error_count > self.config.max_protocol_errors:
                    summary = "local agent exceeded the malformed-response budget"
                    error = summary
                    break
                continue

            action_count += 1
            action_name = str(action["action"])
            if action_name == "finish":
                finish_status = str(action.get("status") or "failed").lower()
                finish_summary = str(action.get("summary") or "local model did not provide a summary").strip()
                if finish_status == "completed":
                    facts = self.executor.completion_facts()
                    if facts["completion_ready"]:
                        status = "completed"
                        summary = finish_summary
                        error = None
                        finish_ok = True
                    else:
                        status = "failed"
                        error = str(facts["reason"])
                        summary = f"unsupported completion claim: {error}"
                        finish_ok = False
                elif finish_status in {"blocked", "failed"}:
                    status = finish_status
                    summary = finish_summary
                    error = finish_summary
                    finish_ok = False
                else:
                    status = "failed"
                    error = f"finish status must be completed, blocked, or failed: {finish_status}"
                    summary = error
                    finish_ok = False
                self._events.append(
                    {
                        "step": step,
                        "action": "finish",
                        "arguments": {"status": finish_status, "summary": finish_summary},
                        "test_first_phase": "record_evidence",
                        "ok": finish_ok,
                        "completion_facts": self.executor.completion_facts(),
                        "error": error,
                    }
                )
                break

            result = self.executor.execute(action, step=step)
            test_first_phase = result.get("test_first_phase")
            if (
                not selection_phase_recorded
                and action_name in {"list_files", "read_file", "search"}
            ):
                test_first_phase = "select_or_generate_tests"
                selection_phase_recorded = True
            elif action_name in {"write_file", "apply_patch"} and result.get("mutated") is True:
                test_first_phase = "implement_change"
            event = {
                "step": step,
                "action": action_name,
                "arguments": _receipt_arguments(action),
                "ok": bool(result.get("ok")),
                "blocked": bool(result.get("blocked")),
                "result": _receipt_result(result, self.config.max_tool_output_chars),
            }
            if isinstance(test_first_phase, str):
                event["test_first_phase"] = test_first_phase
            self._events.append(event)
            history.extend(
                [
                    {"role": "assistant", "content": _bounded(raw_response, self.config.max_tool_output_chars)},
                    {
                        "role": "user",
                        "content": "TOOL_RESULT\n"
                        + json.dumps(_model_result(result), separators=(",", ":"), ensure_ascii=True),
                    },
                ]
            )

        result = LocalAgentRunResult(
            status=status,
            summary=summary,
            error=error,
            observation_hash=self.observation_hash,
            request_digest=self.request_digest,
            started_at=started_at,
            finished_at=utc_now(),
            action_count=action_count,
            protocol_error_count=protocol_error_count,
            blocked_action_count=self.executor.blocked_action_count,
            compaction_count=self._compaction_count,
            completion_facts=self.executor.completion_facts(),
            events=tuple(self._events),
        )
        if self.receipt_path is not None:
            _write_receipt(self.receipt_path, result)
        return result

    def _compact_history_if_needed(
        self,
        base_messages: list[dict[str, str]],
        history: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        if len(self._events) == self._last_compacted_event_count:
            return history
        base_tokens = _estimate_tokens(base_messages)
        threshold = max(
            128,
            int(self.config.context_window_tokens * self.config.compact_ratio)
            - self.config.context_reserve_tokens
            - base_tokens,
        )
        if _estimate_tokens(history) <= threshold:
            return history
        memory = {
            "schema_version": "sisyphus.local_agent_memory.v1",
            "event_count": len(self._events),
            "completion_facts": self.executor.completion_facts(),
            "next_required_action": _next_required_action(self.executor.completion_facts()),
            "blocked_action_count": self.executor.blocked_action_count,
            "recent_events": [
                _compact_event(event, self.config.max_tool_output_chars)
                for event in self._events[-6:]
            ],
        }
        self._compaction_count += 1
        self._last_compacted_event_count = len(self._events)
        return [
            {
                "role": "user",
                "content": "COMPACTED_STATE\n"
                + json.dumps(memory, separators=(",", ":"), ensure_ascii=True),
            }
        ]


def parse_model_action(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("local provider returned an empty action")
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    decoder = json.JSONDecoder()
    parsed: object | None = None
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(parsed, dict):
        raise ValueError("local provider response does not contain a JSON action object")
    action_name = parsed.get("action")
    if not isinstance(action_name, str) or action_name not in LOCAL_AGENT_ACTIONS:
        raise ValueError(f"unknown local agent action: {action_name or '<empty>'}")
    return {str(key): value for key, value in parsed.items()}


def _estimate_tokens(messages: list[dict[str, str]]) -> int:
    serialized = json.dumps(messages, separators=(",", ":"), ensure_ascii=True)
    return max(1, (len(serialized) + 3) // 4)


def _model_result(result: Mapping[str, object]) -> dict[str, object]:
    return {str(key): value for key, value in result.items()}


def _receipt_arguments(action: Mapping[str, object]) -> dict[str, object]:
    arguments: dict[str, object] = {}
    for key, value in action.items():
        if key == "action":
            continue
        if key in {"content", "patch"} and isinstance(value, str):
            arguments[f"{key}_chars"] = len(value)
            continue
        arguments[str(key)] = value
    return arguments


def _receipt_result(result: Mapping[str, object], limit: int) -> dict[str, object]:
    receipt: dict[str, object] = {}
    for key, value in result.items():
        if key == "output" and isinstance(value, str):
            receipt[key] = _bounded(value, min(limit, 1000))
        else:
            receipt[str(key)] = value
    return receipt


def _compact_event(event: Mapping[str, object], limit: int) -> dict[str, object]:
    compact = dict(event)
    result = compact.get("result")
    if isinstance(result, dict):
        compact["result"] = _receipt_result(result, min(limit, 800))
    return compact


def _next_required_action(completion_facts: Mapping[str, object]) -> str:
    if completion_facts.get("completion_ready") is True:
        return "finish with status completed"
    if completion_facts.get("baseline_test_step") is None:
        return "run_test with command_id 0 to record the baseline before any mutation"
    if completion_facts.get("last_mutation_step") is not None:
        return "run_test with a configured command_id; do not repeat an identical write"
    return "inspect repository evidence, then make one scoped write or patch"


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... truncated {len(value) - limit} characters"


def _write_receipt(path: Path, result: LocalAgentRunResult) -> None:
    write_json_file(path, sign_local_agent_receipt(encode_local_agent_run_result(result)))


__all__ = [
    "LOCAL_AGENT_ACTIONS",
    "LOCAL_AGENT_SCHEMA_VERSION",
    "LocalAgentRunResult",
    "LocalCodingAgent",
    "SYSTEM_PROMPT",
    "encode_local_agent_run_result",
    "parse_model_action",
]
