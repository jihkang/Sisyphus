from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import sys

from ....benchmark import BenchmarkFixtureError, default_benchmark_fixture_dir, render_benchmark_markdown, run_benchmark_suite
from ....config import SisyphusConfig
from ....composition.episode_trace import check_episode_trace, read_episode_steps
from ....composition.repository_requests import load_task_record_with_path
from ....dataset_export import export_dataset
from ....eval.loop import run_task_eval_loop
from ....composition.observation import render_task_observation
from ....providers.benchmark import (
    LocalAgentBenchmarkFixtureError,
    default_local_agent_benchmark_fixture_file,
    load_local_agent_benchmark_fixtures,
    render_local_agent_benchmark_markdown,
    run_local_agent_benchmark,
)
from ....providers.local_openai import (
    LocalProviderConfigError,
    is_local_openai_provider,
    parse_local_provider_args,
)
from ....test_first import evaluate_test_first_loop


def handle_observe(*, repo_root: Path, config: SisyphusConfig, task_id: str, as_json: bool) -> int:
    observation = render_task_observation(repo_root=repo_root, config=config, task_id=task_id)
    if as_json:
        print(json.dumps(observation, indent=2))
        return 0

    verification = observation.get("verification", {})
    conformance = observation.get("conformance", {})
    print(f"task: {observation.get('task_id')}")
    print(f"status: {observation.get('status')}")
    print(f"phase: {observation.get('phase')}")
    print(f"plan_status: {observation.get('plan_status')}")
    print(f"spec_status: {observation.get('spec_status')}")
    print(f"verify_status: {verification.get('status') if isinstance(verification, dict) else None}")
    print(f"conformance: {conformance.get('status') if isinstance(conformance, dict) else None}")
    print(f"observation_hash: {observation.get('observation_hash')}")
    allowed = observation.get("allowed_next_actions", [])
    if isinstance(allowed, list) and allowed:
        print("allowed_next_actions:")
        for action in allowed:
            print(f"- {action}")
    forbidden = observation.get("forbidden_next_actions", [])
    if isinstance(forbidden, list) and forbidden:
        print("forbidden_next_actions:")
        for item in forbidden:
            if isinstance(item, dict):
                print(f"- {item.get('action')}: {item.get('reason')}")
    return 0


def handle_episode_check(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    episode_id: str | None,
    as_json: bool,
) -> int:
    _task, task_file = load_task_record_with_path(repo_root, config, task_id)
    summary = check_episode_trace(task_file.parent, task_id=task_id, episode_id=episode_id)
    if as_json:
        print(json.dumps(summary, indent=2))
        return 0 if summary["ok"] else 1

    print(f"episode_check: {task_id}")
    if episode_id:
        print(f"episode_id: {episode_id}")
    print(f"ok: {'yes' if summary['ok'] else 'no'}")
    print(f"episodes: {summary['episode_count']}")
    print(f"steps: {summary['valid_step_count']}/{summary['step_count']}")
    actions = summary.get("actions", [])
    if isinstance(actions, list) and actions:
        print("actions:")
        for action in actions:
            print(f"- {action}")
    errors = summary.get("errors", [])
    if isinstance(errors, list) and errors:
        print("errors:")
        for error in errors:
            if isinstance(error, dict):
                print(f"- {error.get('episode_id')}: {error.get('error')}")
    return 0 if summary["ok"] else 1


def handle_eval_loop(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    episode_id: str | None,
    max_action_count: int,
    as_json: bool,
) -> int:
    result = run_task_eval_loop(
        repo_root,
        config,
        task_id,
        episode_id=episode_id,
        max_action_count=max_action_count,
    )
    payload = result.to_dict()
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"eval_loop: {task_id}")
    print(f"terminal_status: {result.terminal_status}")
    print(f"reward_total: {result.reward.total}")
    print(f"actions: {result.action_count}")
    print("metrics:")
    for name, value in result.metrics.items():
        print(f"- {name}: {value}")
    test_first = payload.get("loop", {}).get("test_first", {}) if isinstance(payload.get("loop"), dict) else {}
    if isinstance(test_first, dict):
        print(f"test_first: {test_first.get('status')}")
    return 0


def handle_eval_test_first(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    episode_id: str | None,
    as_json: bool,
) -> int:
    _task, task_file = load_task_record_with_path(repo_root, config, task_id)
    steps = read_episode_steps(task_file.parent, episode_id=episode_id)
    evaluation = evaluate_test_first_loop(steps)
    payload = {
        "task_id": task_id,
        "episode_id": episode_id,
        "test_first": evaluation.to_dict(),
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"test_first: {task_id}")
    if episode_id:
        print(f"episode_id: {episode_id}")
    print(f"status: {evaluation.status}")
    if evaluation.missing_phases:
        print("missing_phases:")
        for phase in evaluation.missing_phases:
            print(f"- {phase}")
    if evaluation.violations:
        print("violations:")
        for violation in evaluation.violations:
            print(f"- {violation}")
    return 0 if evaluation.status != "violated" else 1


def handle_benchmark_run(*, repo_root: Path, fixtures_dir: str | None, as_json: bool) -> int:
    fixture_path = Path(fixtures_dir) if fixtures_dir else default_benchmark_fixture_dir(repo_root)
    if not fixture_path.is_absolute():
        fixture_path = repo_root / fixture_path
    try:
        result = run_benchmark_suite(fixture_path)
    except BenchmarkFixtureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_benchmark_markdown(result), end="")
    return 0


def handle_local_agent_benchmark(
    *,
    repo_root: Path,
    fixtures_file: str | None,
    provider: str,
    provider_args: list[str] | None,
    output: str | None,
    as_json: bool,
) -> int:
    fixture_path = (
        Path(fixtures_file)
        if fixtures_file
        else default_local_agent_benchmark_fixture_file(repo_root)
    )
    if not fixture_path.is_absolute():
        fixture_path = repo_root / fixture_path
    output_path = Path(output) if output else None
    if output_path is not None and not output_path.is_absolute():
        output_path = repo_root / output_path

    try:
        if not is_local_openai_provider(provider):
            raise LocalProviderConfigError(
                f"local-agent benchmark requires a local provider alias: {provider}"
            )
        config = replace(
            parse_local_provider_args(provider, provider_args),
            fallback_provider=None,
        )
        fixtures = load_local_agent_benchmark_fixtures(fixture_path)
        result = run_local_agent_benchmark(fixtures, config)
        rendered = (
            json.dumps(result.to_dict(), indent=2) + "\n"
            if as_json
            else render_local_agent_benchmark_markdown(result)
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered, encoding="utf-8")
    except (LocalAgentBenchmarkFixtureError, LocalProviderConfigError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(rendered, end="")
    return 0 if result.passed else 1


def handle_dataset_export(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    format: str,
    task_id: str | None,
    output: str | None,
    max_action_count: int,
) -> int:
    output_path = Path(output) if output else None
    if output_path is not None and not output_path.is_absolute():
        output_path = repo_root / output_path
    result = export_dataset(
        repo_root,
        config,
        format=format,
        task_id=task_id,
        output_path=output_path,
        max_action_count=max_action_count,
    )
    if output_path is None:
        print(result.to_jsonl(), end="")
    else:
        print(json.dumps(result.summary(), indent=2))
    return 0


__all__ = [
    "handle_benchmark_run",
    "handle_dataset_export",
    "handle_episode_check",
    "handle_eval_loop",
    "handle_eval_test_first",
    "handle_local_agent_benchmark",
    "handle_observe",
]
