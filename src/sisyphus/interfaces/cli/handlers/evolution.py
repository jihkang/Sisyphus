from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

from ....config import SisyphusConfig
from ....composition.evolution_operator import (
    evaluate_evolution_followup_decision,
    request_evolution_followup,
)
from ....composition.evolution_surface import (
    execute_evolution_surface,
    load_evolution_run_artifacts,
)
from ....evolution.presentation import (
    compare_evolution_runs,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from ..parsing import parse_evidence_summary_json, parse_verification_obligation_json


def handle_evolution_run(
    *,
    repo_root: Path,
    run_id: str,
    load_artifacts=load_evolution_run_artifacts,
    render_overview=render_evolution_run_overview,
) -> int:
    try:
        artifacts = load_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_overview(artifacts), end="")
    return 0


def handle_evolution_execute(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    run_id: str | None,
    target_ids: Sequence[str] | None,
    task_ids: Sequence[str] | None,
    max_events: int,
    execute_surface=execute_evolution_surface,
) -> int:
    result = execute_surface(
        repo_root,
        run_id=run_id,
        target_ids=target_ids,
        task_ids=task_ids,
        max_events=max_events,
        config=config,
    )
    if result.ok:
        print(result.content, end="" if result.content.endswith("\n") else "\n")
        return 0
    print(f"error: {result.error or 'evolution execute failed'}", file=sys.stderr)
    if result.run_id:
        print(f"run_id: {result.run_id}", file=sys.stderr)
    if result.artifact_dir:
        print(f"artifact_dir: {result.artifact_dir}", file=sys.stderr)
    if result.failure_stage:
        print(f"failure_stage: {result.failure_stage}", file=sys.stderr)
    if result.error_type:
        print(f"error_type: {result.error_type}", file=sys.stderr)
    return 1


def handle_evolution_request_followup(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    run_id: str,
    candidate_id: str,
    title: str,
    summary: str,
    requested_task_type: str,
    slug: str | None,
    target_ids: Sequence[str] | None,
    owned_paths: Sequence[str] | None,
    review_gates: Sequence[str] | None,
    verification_obligation_json: list[str] | None,
    evidence_summary_json: list[str] | None,
    request_followup=request_evolution_followup,
) -> int:
    try:
        result = request_followup(
            repo_root,
            run_id=run_id,
            candidate_id=candidate_id,
            title=title,
            summary=summary,
            requested_task_type=requested_task_type,
            slug=slug,
            target_ids=target_ids,
            owned_paths=owned_paths,
            review_gates=review_gates,
            verification_obligations=parse_verification_obligation_json(verification_obligation_json),
            evidence_summary=parse_evidence_summary_json(evidence_summary_json),
            config=config,
        )
    except (FileNotFoundError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.content, end="" if result.content.endswith("\n") else "\n")
    return 0


def handle_evolution_decide(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    claim: str | None,
    decide_followup=evaluate_evolution_followup_decision,
) -> int:
    try:
        result = decide_followup(
            repo_root,
            task_id=task_id,
            claim=claim,
            config=config,
        )
    except (FileNotFoundError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.content, end="" if result.content.endswith("\n") else "\n")
    return 0


def handle_evolution_status(
    *,
    repo_root: Path,
    run_id: str,
    load_artifacts=load_evolution_run_artifacts,
    render_status=render_evolution_run_status,
) -> int:
    try:
        artifacts = load_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_status(artifacts), end="")
    return 0


def handle_evolution_report(
    *,
    repo_root: Path,
    run_id: str,
    load_artifacts=load_evolution_run_artifacts,
    render_report=render_evolution_run_report,
) -> int:
    try:
        artifacts = load_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_report(artifacts), end="")
    return 0


def handle_evolution_compare(
    *,
    repo_root: Path,
    left_run_id: str,
    right_run_id: str,
    load_artifacts=load_evolution_run_artifacts,
    compare_runs=compare_evolution_runs,
    render_compare=render_evolution_run_compare,
) -> int:
    try:
        left = load_artifacts(repo_root, left_run_id)
        right = load_artifacts(repo_root, right_run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    comparison = compare_runs(left, right)
    print(render_compare(comparison), end="")
    return 0


__all__ = [
    "handle_evolution_compare",
    "handle_evolution_decide",
    "handle_evolution_execute",
    "handle_evolution_report",
    "handle_evolution_request_followup",
    "handle_evolution_run",
    "handle_evolution_status",
]
