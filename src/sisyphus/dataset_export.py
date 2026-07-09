from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .config import SisyphusConfig
from .episode_trace import read_episode_steps
from .eval.loop import build_task_eval_loop_result
from .state import list_task_records, load_task_record


DATASET_EXPORT_SCHEMA_VERSION = "sisyphus.dataset_export.v1"
DATASET_FORMAT_SFT = "sft"
DATASET_FORMAT_RL = "rl"
DATASET_FORMATS = (DATASET_FORMAT_SFT, DATASET_FORMAT_RL)
SFT_SYSTEM_PROMPT = "You are a software-workflow agent operating inside Sisyphus."


@dataclass(frozen=True, slots=True)
class DatasetExportResult:
    format: str
    records: tuple[dict[str, object], ...]
    task_ids: tuple[str, ...]
    output_path: Path | None = None

    @property
    def record_count(self) -> int:
        return len(self.records)

    def to_jsonl(self) -> str:
        lines = [json.dumps(record, separators=(",", ":"), sort_keys=True) for record in self.records]
        return "\n".join(lines) + ("\n" if lines else "")

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": DATASET_EXPORT_SCHEMA_VERSION,
            "format": self.format,
            "record_count": self.record_count,
            "task_ids": list(self.task_ids),
            "output_path": str(self.output_path) if self.output_path is not None else None,
        }


def export_dataset(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    format: str,
    task_id: str | None = None,
    output_path: Path | None = None,
    max_action_count: int = 50,
) -> DatasetExportResult:
    result = build_dataset_export(
        repo_root,
        config,
        format=format,
        task_id=task_id,
        max_action_count=max_action_count,
    )
    if output_path is None:
        return result
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_jsonl(), encoding="utf-8")
    return DatasetExportResult(
        format=result.format,
        records=result.records,
        task_ids=result.task_ids,
        output_path=output_path,
    )


def build_dataset_export(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    format: str,
    task_id: str | None = None,
    max_action_count: int = 50,
) -> DatasetExportResult:
    _validate_format(format)
    task_entries = _selected_task_entries(repo_root, config, task_id=task_id)
    records: list[dict[str, object]] = []
    task_ids: list[str] = []
    for task, task_dir in task_entries:
        current_task_id = str(task.get("id") or "")
        if current_task_id:
            task_ids.append(current_task_id)
        records.extend(
            build_task_dataset_records(
                task,
                task_dir,
                format=format,
                max_action_count=max_action_count,
            )
        )
    return DatasetExportResult(
        format=format,
        records=tuple(records),
        task_ids=tuple(task_ids),
    )


def build_task_dataset_records(
    task: dict[str, object],
    task_dir: Path,
    *,
    format: str,
    max_action_count: int = 50,
) -> tuple[dict[str, object], ...]:
    _validate_format(format)
    steps = [step for step in read_episode_steps(task_dir) if _has_action(step)]
    if not steps:
        return ()

    records: list[dict[str, object]] = []
    for episode_id in _episode_ids(steps):
        eval_result = build_task_eval_loop_result(
            task,
            task_dir,
            episode_id=episode_id,
            max_action_count=max_action_count,
        )
        for step in _episode_action_steps(steps, episode_id):
            if format == DATASET_FORMAT_SFT:
                records.append(_sft_record(task, step, eval_result.to_dict()))
            else:
                records.append(_rl_record(task, step, eval_result.to_dict()))
    return tuple(records)


def _selected_task_entries(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str | None,
) -> tuple[tuple[dict[str, object], Path], ...]:
    if task_id:
        task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
        return ((task, task_file.parent),)

    entries: list[tuple[dict[str, object], Path]] = []
    for task in sorted(list_task_records(repo_root, config.task_dir), key=lambda item: str(item.get("id") or "")):
        task_dir_value = str(task.get("task_dir") or "")
        if not task_dir_value:
            continue
        task_dir = repo_root / task_dir_value
        if read_episode_steps(task_dir):
            entries.append((task, task_dir))
    return tuple(entries)


def _sft_record(task: dict[str, object], step: dict[str, object], eval_payload: dict[str, object]) -> dict[str, object]:
    action = _action(step)
    return {
        "schema_version": DATASET_EXPORT_SCHEMA_VERSION,
        "format": DATASET_FORMAT_SFT,
        "task_id": task.get("id"),
        "episode_id": step.get("episode_id"),
        "step": step.get("step"),
        "messages": [
            {
                "role": "system",
                "content": SFT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(_observation_payload(step), separators=(",", ":"), sort_keys=True),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "action": action.get("name"),
                        "arguments": action.get("arguments", {}),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            },
        ],
        "result": _result(step),
        "terminal_status": _terminal_status(eval_payload),
        "reward": _reward_payload(eval_payload),
        "test_first": _test_first_payload(eval_payload),
    }


def _rl_record(task: dict[str, object], step: dict[str, object], eval_payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": DATASET_EXPORT_SCHEMA_VERSION,
        "format": DATASET_FORMAT_RL,
        "task_id": task.get("id"),
        "episode_id": step.get("episode_id"),
        "step": step.get("step"),
        "timestamp": step.get("timestamp"),
        "observation": _observation_payload(step),
        "action": _action(step),
        "result": _result(step),
        "transition": {
            "state_after": step.get("state_after") if isinstance(step.get("state_after"), dict) else {},
            "state_diff": step.get("state_diff") if isinstance(step.get("state_diff"), dict) else {},
        },
        "terminal_status": _terminal_status(eval_payload),
        "reward": _reward_payload(eval_payload),
        "metrics": eval_payload.get("metrics") if isinstance(eval_payload.get("metrics"), dict) else {},
        "test_first": _test_first_payload(eval_payload),
    }


def _observation_payload(step: dict[str, object]) -> dict[str, object]:
    return {
        "state_ref": step.get("state_ref"),
        "observation_hash": step.get("observation_hash"),
        "state_before": step.get("state_before") if isinstance(step.get("state_before"), dict) else {},
    }


def _reward_payload(eval_payload: dict[str, object]) -> dict[str, object]:
    reward = eval_payload.get("reward")
    if not isinstance(reward, dict):
        return {"total": 0.0, "components": {}, "penalties": {}}
    return {
        "total": reward.get("total", 0.0),
        "components": reward.get("components") if isinstance(reward.get("components"), dict) else {},
        "penalties": reward.get("penalties") if isinstance(reward.get("penalties"), dict) else {},
    }


def _terminal_status(eval_payload: dict[str, object]) -> str:
    outcome = eval_payload.get("outcome")
    if isinstance(outcome, dict):
        value = outcome.get("terminal_status")
        if isinstance(value, str):
            return value
    return "unknown"


def _test_first_payload(eval_payload: dict[str, object]) -> dict[str, object]:
    loop = eval_payload.get("loop")
    if isinstance(loop, dict):
        test_first = loop.get("test_first")
        if isinstance(test_first, dict):
            return test_first
    return {}


def _action(step: dict[str, object]) -> dict[str, object]:
    action = step.get("action")
    return dict(action) if isinstance(action, dict) else {}


def _result(step: dict[str, object]) -> dict[str, object]:
    result = step.get("result")
    return dict(result) if isinstance(result, dict) else {}


def _has_action(step: dict[str, object]) -> bool:
    action = step.get("action")
    return isinstance(action, dict) and bool(action.get("name"))


def _episode_ids(steps: Iterable[dict[str, object]]) -> tuple[str, ...]:
    return tuple(sorted({str(step.get("episode_id")) for step in steps if step.get("episode_id")}))


def _episode_action_steps(steps: Iterable[dict[str, object]], episode_id: str) -> tuple[dict[str, object], ...]:
    return tuple(
        sorted(
            (step for step in steps if str(step.get("episode_id")) == episode_id),
            key=lambda step: (_int_field(step, "step"), _int_field(step, "line")),
        )
    )


def _int_field(step: dict[str, object], name: str) -> int:
    value = step.get(name)
    return value if isinstance(value, int) else 0


def _validate_format(format: str) -> None:
    if format not in DATASET_FORMATS:
        raise ValueError(f"unsupported dataset export format: {format}")


__all__ = [
    "DATASET_EXPORT_SCHEMA_VERSION",
    "DATASET_FORMAT_RL",
    "DATASET_FORMAT_SFT",
    "DATASET_FORMATS",
    "DatasetExportResult",
    "build_dataset_export",
    "build_task_dataset_records",
    "export_dataset",
]
