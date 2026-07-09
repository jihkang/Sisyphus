from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

from ...config import SisyphusConfig
from ...evolution.handoff import EvolutionEvidenceSummary, EvolutionVerificationObligation
from ...evolution.operator import (
    evaluate_evolution_followup_decision,
    request_evolution_followup,
)
from ...evolution.surface import (
    compare_evolution_runs,
    execute_evolution_surface,
    load_evolution_run_artifacts,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from ...shared.coerce import optional_str, optional_str_list
from .coercion import dict_list


def _evolution_run(
    *,
    repo_root: Path,
    args: dict[str, object],
    load_artifacts=load_evolution_run_artifacts,
    render_overview=render_evolution_run_overview,
    **_: object,
) -> dict[str, object]:
    run_id = str(args["run_id"])
    artifacts = load_artifacts(repo_root, run_id)
    return {
        "run_id": run_id,
        "resource_uri": evolution_run_uri(run_id, "run"),
        "content": render_overview(artifacts),
    }


def _evolution_status(
    *,
    repo_root: Path,
    args: dict[str, object],
    load_artifacts=load_evolution_run_artifacts,
    render_status=render_evolution_run_status,
    **_: object,
) -> dict[str, object]:
    run_id = str(args["run_id"])
    artifacts = load_artifacts(repo_root, run_id)
    return {
        "run_id": run_id,
        "resource_uri": evolution_run_uri(run_id, "status"),
        "content": render_status(artifacts),
    }


def _evolution_report(
    *,
    repo_root: Path,
    args: dict[str, object],
    load_artifacts=load_evolution_run_artifacts,
    render_report=render_evolution_run_report,
    **_: object,
) -> dict[str, object]:
    run_id = str(args["run_id"])
    artifacts = load_artifacts(repo_root, run_id)
    return {
        "run_id": run_id,
        "resource_uri": evolution_run_uri(run_id, "report"),
        "content": render_report(artifacts),
    }


def _evolution_compare(
    *,
    repo_root: Path,
    args: dict[str, object],
    load_artifacts=load_evolution_run_artifacts,
    compare_runs=compare_evolution_runs,
    render_compare=render_evolution_run_compare,
    **_: object,
) -> dict[str, object]:
    left_run_id = str(args["left_run_id"])
    right_run_id = str(args["right_run_id"])
    left = load_artifacts(repo_root, left_run_id)
    right = load_artifacts(repo_root, right_run_id)
    comparison = compare_runs(left, right)
    return {
        "left_run_id": left_run_id,
        "right_run_id": right_run_id,
        "resource_uri": evolution_compare_uri(left_run_id, right_run_id),
        "content": render_compare(comparison),
    }


def _evolution_execute(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    execute_surface=execute_evolution_surface,
    **_: object,
) -> dict[str, object]:
    result = execute_surface(
        repo_root,
        run_id=optional_str(args.get("run_id")),
        target_ids=optional_str_list(args.get("target_ids")),
        task_ids=optional_str_list(args.get("task_ids")),
        max_events=int(args.get("max_events", 50)),
        config=config,
    )
    return {
        "ok": result.ok,
        "run_id": result.run_id,
        "resource_uri": result.resource_uri,
        "artifact_dir": result.artifact_dir,
        "final_stage": result.final_stage,
        "failure_stage": result.failure_stage,
        "content": result.content,
        "error": result.error,
        "error_type": result.error_type,
    }


def _evolution_followup_request(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    request_followup=request_evolution_followup,
    **_: object,
) -> dict[str, object]:
    result = request_followup(
        repo_root,
        run_id=str(args["run_id"]),
        candidate_id=str(args["candidate_id"]),
        title=str(args["title"]),
        summary=str(args["summary"]),
        requested_task_type=str(args.get("requested_task_type", "feature")),
        slug=optional_str(args.get("slug")),
        target_ids=optional_str_list(args.get("target_ids")),
        owned_paths=optional_str_list(args.get("owned_paths")),
        review_gates=optional_str_list(args.get("review_gates")),
        verification_obligations=verification_obligations(args.get("verification_obligations")),
        evidence_summary=evidence_summary(args.get("evidence_summary")),
        config=config,
    )
    return {
        "task_id": result.task_id,
        "task_uri": result.task_uri,
        "run_id": result.run_id,
        "candidate_id": result.candidate_id,
        "requested_targets": list(result.requested_targets),
        "required_review_gates": list(result.required_review_gates),
        "content": result.content,
    }


def _evolution_decide(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    decide_followup=evaluate_evolution_followup_decision,
    **_: object,
) -> dict[str, object]:
    result = decide_followup(
        repo_root,
        task_id=str(args["task_id"]),
        claim=optional_str(args.get("claim")),
        config=config,
    )
    return {
        "task_id": result.task_id,
        "task_uri": result.task_uri,
        "run_id": result.run_id,
        "candidate_id": result.candidate_id,
        "gate_status": result.gate_status,
        "envelope_status": result.envelope_status,
        "content": result.content,
    }


TOOL_EXECUTORS = MappingProxyType(
    {
        "sisyphus.evolution_run": _evolution_run,
        "sisyphus.evolution_status": _evolution_status,
        "sisyphus.evolution_report": _evolution_report,
        "sisyphus.evolution_compare": _evolution_compare,
        "sisyphus.evolution_execute": _evolution_execute,
        "sisyphus.evolution_followup_request": _evolution_followup_request,
        "sisyphus.evolution_decide": _evolution_decide,
    }
)


def call_evolution_tool(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    tool_name: str,
    args: dict[str, object],
    load_artifacts=load_evolution_run_artifacts,
    render_overview=render_evolution_run_overview,
    render_status=render_evolution_run_status,
    render_report=render_evolution_run_report,
    compare_runs=compare_evolution_runs,
    render_compare=render_evolution_run_compare,
    execute_surface=execute_evolution_surface,
    request_followup=request_evolution_followup,
    decide_followup=evaluate_evolution_followup_decision,
) -> dict[str, object] | None:
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return None
    return executor(
        repo_root=repo_root,
        config=config,
        args=args,
        load_artifacts=load_artifacts,
        render_overview=render_overview,
        render_status=render_status,
        render_report=render_report,
        compare_runs=compare_runs,
        render_compare=render_compare,
        execute_surface=execute_surface,
        request_followup=request_followup,
        decide_followup=decide_followup,
    )


def verification_obligations(
    value: object,
) -> tuple[EvolutionVerificationObligation, ...] | None:
    raw_items = dict_list(value)
    if raw_items is None:
        return None
    normalized: list[EvolutionVerificationObligation] = []
    for index, item in enumerate(raw_items, start=1):
        claim = str(item.get("claim", "")).strip()
        method = str(item.get("method", "")).strip()
        if not claim or not method:
            raise ValueError(
                f"verification_obligations[{index}] requires non-empty claim and method"
            )
        normalized.append(
            EvolutionVerificationObligation(
                claim=claim,
                method=method,
                required=bool(item.get("required", True)),
            )
        )
    return tuple(normalized)


def evidence_summary(value: object) -> tuple[EvolutionEvidenceSummary, ...] | None:
    raw_items = dict_list(value)
    if raw_items is None:
        return None
    normalized: list[EvolutionEvidenceSummary] = []
    for index, item in enumerate(raw_items, start=1):
        kind = str(item.get("kind", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not kind or not summary:
            raise ValueError(
                f"evidence_summary[{index}] requires non-empty kind and summary"
            )
        normalized.append(
            EvolutionEvidenceSummary(
                kind=kind,
                summary=summary,
                locator=optional_str(item.get("locator")),
            )
        )
    return tuple(normalized)


def evolution_run_uri(run_id: str, view: str) -> str:
    return f"evolution://{run_id}/{view}"


def evolution_compare_uri(left_run_id: str, right_run_id: str) -> str:
    return f"evolution://compare/{left_run_id}/{right_run_id}"


def read_evolution_resource(
    repo_root: Path,
    parsed,
    *,
    load_artifacts=load_evolution_run_artifacts,
    compare_runs=compare_evolution_runs,
    render_compare=render_evolution_run_compare,
    render_overview=render_evolution_run_overview,
    render_status=render_evolution_run_status,
    render_report=render_evolution_run_report,
) -> str:
    if parsed.netloc == "compare":
        left_run_id, right_run_id = parse_compare_path(parsed.path)
        left = load_artifacts(repo_root, left_run_id)
        right = load_artifacts(repo_root, right_run_id)
        comparison = compare_runs(left, right)
        return render_compare(comparison)

    run_id = parsed.netloc
    resource_name = parsed.path.lstrip("/")
    if not run_id:
        raise ValueError("evolution resource must include a run id")
    artifacts = load_artifacts(repo_root, run_id)
    if resource_name == "run":
        return render_overview(artifacts)
    if resource_name == "status":
        return render_status(artifacts)
    if resource_name == "report":
        return render_report(artifacts)
    raise ValueError(f"unsupported evolution resource `{resource_name}`")


def parse_compare_path(path: str) -> tuple[str, str]:
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("evolution compare resource must include left and right run ids")
    return parts[0], parts[1]


__all__ = [
    "TOOL_EXECUTORS",
    "call_evolution_tool",
    "evidence_summary",
    "evolution_compare_uri",
    "evolution_run_uri",
    "parse_compare_path",
    "read_evolution_resource",
    "verification_obligations",
]
