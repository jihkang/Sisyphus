from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .bus import build_event_publisher
from .conformance import (
    CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
    CONFORMANCE_GREEN,
    CONFORMANCE_YELLOW,
    append_conformance_log,
    collect_conformance_gates,
)
from .config import SisyphusConfig
from .design import (
    DESIGN_ASSESSMENT_APPROPRIATE,
    DESIGN_ASSESSMENT_OVERDESIGNED,
    DESIGN_ASSESSMENT_UNDERDESIGNED,
    DESIGN_MODE_NONE,
    evaluate_design_adequacy,
    ensure_task_design_defaults,
)
from .events import new_event_envelope
from .planning import collect_plan_gates, reopen_task_plan_for_design_replan
from .state import load_task_record, save_task_record, utc_now
from .strategy import sync_test_strategy_from_docs


VERIFY_GATE_CODES = {
    "SPEC_INCOMPLETE",
    "ACCEPTANCE_CRITERIA_MISSING",
    "VERIFICATION_MAPPING_MISSING",
    "EXTERNAL_LLM_POLICY_MISSING",
    "VERIFY_FAILED",
    "DOC_INCOMPLETE",
    "REPRO_MISSING",
    "REGRESSION_TEST_MISSING",
    "AUDIT_LIMIT_REACHED",
    "TEST_STRATEGY_MISSING",
    "EXTERNAL_LLM_REVIEW_REQUIRED",
    "PLAN_APPROVAL_REQUIRED",
    "PLAN_CHANGES_REQUESTED",
    "DESIGN_REPLAN_REQUIRED",
    "DESIGN_ARTIFACTS_MISSING",
}

TRANSIENT_GATE_SOURCES = {
    "verify",
    "docs",
    "strategy",
    "design",
    "close",
    "plan",
    "conformance",
}


@dataclass(slots=True)
class VerifyOutcome:
    task_id: str
    status: str
    stage: str
    audit_attempts: int
    max_audit_attempts: int
    gates: list[dict]
    command_results: list[dict]
    verify_file: Path


def run_verify(repo_root: Path, config: SisyphusConfig, task_id: str) -> VerifyOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent
    task = sync_test_strategy_from_docs(task=task, task_dir=task_dir)
    _evaluate_and_record_design(task)

    task["audit_attempts"] = int(task.get("audit_attempts", 0)) + 1
    task["updated_at"] = utc_now()
    task["stage"] = "audit"

    gates = [
        gate
        for gate in task.get("gates", [])
        if gate.get("code") not in VERIFY_GATE_CODES and gate.get("source") not in TRANSIENT_GATE_SOURCES
    ]
    gates.extend(_collect_doc_gates(task, task_dir))
    spec_gates = _collect_spec_gates(task, task_dir)
    gates.extend(spec_gates)
    design_gates = _collect_design_gates(task)
    gates.extend(design_gates)
    plan_gates = collect_plan_gates(task, action="verify")
    gates.extend(plan_gates)
    conformance_gates = collect_conformance_gates(task, action="verify")
    gates.extend(conformance_gates)

    command_results: list[dict] = []
    if not spec_gates and not design_gates and not plan_gates and not conformance_gates:
        task["stage"] = "audit"
        gates.extend(_collect_test_strategy_gates(task))
        command_results = _run_verify_commands(task, task_dir)
    task["last_verify_results"] = command_results
    task["last_verified_at"] = utc_now()

    if any(result["status"] == "failed" for result in command_results):
        gates.append(_gate("VERIFY_FAILED", "one or more verify commands failed", source="verify"))

    if task["audit_attempts"] >= int(task.get("max_audit_attempts", 10)):
        gates.append(_gate("AUDIT_LIMIT_REACHED", "maximum audit attempts reached", source="verify"))

    task["gates"] = _dedupe_gates(gates)
    passed = len(task["gates"]) == 0
    task["verify_status"] = "passed" if passed else "failed"
    task["status"] = "verified" if passed else "blocked"
    if passed:
        task["stage"] = "done"
        task["workflow_phase"] = "verified"
    elif spec_gates:
        task["stage"] = "spec"
    elif design_gates:
        task["stage"] = "plan_review"
    elif plan_gates:
        task["stage"] = "plan_review"
    elif conformance_gates:
        task["stage"] = "audit"
    else:
        task["stage"] = "audit"

    verify_file = task_dir / task["docs"]["verify"]
    verify_file.write_text(_render_verify_markdown(task, command_results), encoding="utf-8")
    save_task_record(task_file=task_file, task=task)
    build_event_publisher(repo_root, config).publish(
        new_event_envelope(
            "verify.completed",
            source={"module": "audit"},
            data={
                "task_id": task["id"],
                "status": task["verify_status"],
                "stage": task["stage"],
                "gate_count": len(task["gates"]),
            },
        )
    )

    return VerifyOutcome(
        task_id=task["id"],
        status=task["verify_status"],
        stage=task["stage"],
        audit_attempts=task["audit_attempts"],
        max_audit_attempts=task["max_audit_attempts"],
        gates=task["gates"],
        command_results=command_results,
        verify_file=verify_file,
    )


def _collect_doc_gates(task: dict, task_dir: Path) -> list[dict]:
    gates: list[dict] = []
    required_doc_keys = ["brief"]
    if task["type"] == "feature":
        required_doc_keys.append("plan")
    else:
        required_doc_keys.extend(["repro", "fix_plan"])

    for key in required_doc_keys:
        relative_path = task["docs"].get(key)
        if not relative_path:
            gates.append(_gate("DOC_INCOMPLETE", f"{key} document is missing from task metadata", source="docs"))
            continue
        doc_path = task_dir / relative_path
        if not doc_path.exists():
            gates.append(_gate("DOC_INCOMPLETE", f"{relative_path} does not exist", source="docs"))
            continue
        content = doc_path.read_text(encoding="utf-8").strip()
        if _looks_like_unfilled_template(content):
            gates.append(_gate("DOC_INCOMPLETE", f"{relative_path} is incomplete", source="docs"))

    if task["type"] == "issue":
        repro_content = (task_dir / task["docs"]["repro"]).read_text(encoding="utf-8")
        if "Regression Test Target" in repro_content and "Describe the test" in repro_content:
            gates.append(_gate("REGRESSION_TEST_MISSING", "issue task is missing a regression test target", source="docs"))

    return gates


def _collect_spec_gates(task: dict, task_dir: Path) -> list[dict]:
    gates: list[dict] = []
    brief_path = task_dir / task["docs"]["brief"]
    brief_content = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""

    if task["type"] == "feature":
        if "Criterion 1" in brief_content or "- [ ] Criterion 1" in brief_content:
            gates.append(_gate("ACCEPTANCE_CRITERIA_MISSING", "feature task requires filled acceptance criteria", source="docs"))
    else:
        repro_path = task_dir / task["docs"]["repro"]
        repro_content = repro_path.read_text(encoding="utf-8") if repro_path.exists() else ""
        if "1. Step 1" in repro_content or "Describe the test" in repro_content:
            gates.append(_gate("SPEC_INCOMPLETE", "issue repro and regression target must be completed before audit", source="docs"))

    strategy = task.get("test_strategy", {})
    if not strategy.get("normal_cases") or not strategy.get("edge_cases") or not strategy.get("exception_cases"):
        gates.append(_gate("SPEC_INCOMPLETE", "task spec must define normal, edge, and exception cases before audit", source="strategy"))

    if not strategy.get("verification_methods"):
        gates.append(_gate("VERIFICATION_MAPPING_MISSING", "verification mapping must be completed before audit", source="strategy"))

    external_llm = strategy.get("external_llm", {})
    if external_llm.get("required") and (
        not external_llm.get("provider") or
        not external_llm.get("purpose") or
        not external_llm.get("trigger")
    ):
        gates.append(_gate("EXTERNAL_LLM_POLICY_MISSING", "external LLM review policy must be fully defined", source="strategy"))

    return gates


def _collect_design_gates(task: dict) -> list[dict]:
    ensure_task_design_defaults(task)
    design = task.get("design", {})
    assessment = design.get("assessment", {})
    missing_artifacts = list(assessment.get("missing_artifacts") or [])
    gates: list[dict] = []

    if assessment.get("status") == DESIGN_ASSESSMENT_UNDERDESIGNED:
        gates.append(_gate("DESIGN_REPLAN_REQUIRED", "design assessment requires a plan revision before verify", source="design"))
    if missing_artifacts:
        gates.append(
            _gate(
                "DESIGN_ARTIFACTS_MISSING",
                f"missing required design artifacts: {', '.join(missing_artifacts)}",
                source="design",
            )
        )
    return gates


def _collect_test_strategy_gates(task: dict) -> list[dict]:
    strategy = task.get("test_strategy", {})
    gates: list[dict] = []
    normal_cases = strategy.get("normal_cases", [])
    edge_cases = strategy.get("edge_cases", [])
    exception_cases = strategy.get("exception_cases", [])
    verification_methods = strategy.get("verification_methods", [])
    external_llm = strategy.get("external_llm", {})

    if not normal_cases or not edge_cases or not exception_cases or not verification_methods:
        gates.append(_gate("TEST_STRATEGY_MISSING", "normal, edge, exception cases and verification methods must be defined", source="strategy"))

    if task["type"] == "issue" and not normal_cases:
        gates.append(_gate("REPRO_MISSING", "issue task requires explicit regression-oriented test coverage", source="strategy"))

    if external_llm.get("required") and external_llm.get("status") != "passed":
        gates.append(_gate("EXTERNAL_LLM_REVIEW_REQUIRED", "required external LLM review is not complete", source="strategy"))

    return gates


def _run_verify_commands(task: dict, task_dir: Path) -> list[dict]:
    results: list[dict] = []
    for command in task.get("verify_commands", []):
        started_at = utc_now()
        completed = subprocess.run(
            command,
            cwd=task_dir,
            shell=True,
            capture_output=True,
            text=True,
        )
        finished_at = utc_now()
        output_excerpt = (completed.stdout or completed.stderr or "").strip().splitlines()
        excerpt = output_excerpt[-1] if output_excerpt else ""
        results.append(
            {
                "name": command,
                "command": command,
                "status": "passed" if completed.returncode == 0 else "failed",
                "exit_code": completed.returncode,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": None,
                "output_excerpt": excerpt[:200],
            }
        )
    return results


def _render_verify_markdown(task: dict, command_results: list[dict]) -> str:
    passed = task["verify_status"] == "passed"
    result_line = "go next task" if passed else "return to current task"
    strategy = task.get("test_strategy", {})
    external_llm = strategy.get("external_llm", {})
    ensure_task_design_defaults(task)
    design = task.get("design", {})
    assessment = design.get("assessment", {})
    missing_artifacts = list(assessment.get("missing_artifacts") or [])

    command_lines = []
    if command_results:
        for result in command_results:
            command_lines.append(f"- `{result['command']}` -> `{result['status']}`")
    else:
        command_lines.append("- No verify commands configured")

    gate_lines = [f"- `{gate['code']}`: {gate['message']}" for gate in task.get("gates", [])] or ["- None"]

    return "\n".join(
        [
            "# Verify",
            "",
            "## Audit Summary",
            "",
            f"- Attempt: `{task['audit_attempts']}/{task['max_audit_attempts']}`",
            f"- Stage: `{task['stage']}`",
            f"- Status: `{task['verify_status']}`",
            f"- Result: `{result_line}`",
            "",
            "## Command Results",
            "",
            *command_lines,
            "",
            "## Test Coverage Check",
            "",
            f"- Normal cases defined: `{'yes' if strategy.get('normal_cases') else 'no'}`",
            f"- Edge cases defined: `{'yes' if strategy.get('edge_cases') else 'no'}`",
            f"- Exception cases defined: `{'yes' if strategy.get('exception_cases') else 'no'}`",
            f"- Verification methods defined: `{'yes' if strategy.get('verification_methods') else 'no'}`",
            "",
            "## Design Assessment",
            "",
            f"- Mode: `{design.get('mode', DESIGN_MODE_NONE)}`",
            f"- Layer impact: `{design.get('layer_impact', 'layer-preserving')}`",
            f"- Status: `{assessment.get('status', 'not_assessed')}`",
            f"- Replan required: `{'yes' if assessment.get('replan_required') else 'no'}`",
            f"- Missing artifacts: `{', '.join(missing_artifacts) if missing_artifacts else 'none'}`",
            f"- Summary: `{assessment.get('summary') or 'n/a'}`",
            "",
            "## External LLM Review",
            "",
            f"- Required: `{'yes' if external_llm.get('required') else 'no'}`",
            f"- Status: `{external_llm.get('status', 'not_needed')}`",
            f"- Provider: `{external_llm.get('provider') or 'n/a'}`",
            f"- Purpose: `{external_llm.get('purpose') or 'n/a'}`",
            f"- Trigger: `{external_llm.get('trigger') or 'n/a'}`",
            "",
            "## Gates",
            "",
            *gate_lines,
            "",
        ]
    )


def _gate(code: str, message: str, source: str) -> dict:
    return {
        "code": code,
        "message": message,
        "blocking": True,
        "source": source,
        "created_at": utc_now(),
    }


def _dedupe_gates(gates: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for gate in gates:
        key = (gate.get("code", ""), gate.get("message", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gate)
    return deduped


def _looks_like_unfilled_template(content: str) -> bool:
    if not content:
        return True
    placeholder_markers = [
        "Describe the problem",
        "Describe what is broken",
        "Describe the expected result",
        "Hypothesis 1",
        "Step 1",
        "Criterion 1",
        "Risk 1",
        "yes/no",
        "codex/claude/other",
        "none | light | full",
        "layer-preserving | layer-touching | layer-reshaping | layer-adding",
    ]
    return any(marker in content for marker in placeholder_markers)


def _evaluate_and_record_design(task: dict) -> None:
    ensure_task_design_defaults(task)
    previous_status = str(task.get("design", {}).get("assessment", {}).get("status") or "")
    assessment = evaluate_design_adequacy(task)
    status = str(assessment.get("status") or "")
    summary = str(assessment.get("summary") or "design adequacy evaluated")

    if status == DESIGN_ASSESSMENT_UNDERDESIGNED:
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
            status=CONFORMANCE_YELLOW,
            summary=summary,
            source="audit.design",
            resolved=False,
            drift=0,
        )
        reopen_task_plan_for_design_replan(
            task,
            actor="design-audit",
            notes=assessment.get("escalation_reason") or summary,
        )
        return

    if status in {DESIGN_ASSESSMENT_APPROPRIATE, DESIGN_ASSESSMENT_OVERDESIGNED}:
        append_conformance_log(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
            status=CONFORMANCE_GREEN,
            summary=summary,
            source="audit.design",
            resolved=(previous_status == DESIGN_ASSESSMENT_UNDERDESIGNED),
            drift=0,
        )
