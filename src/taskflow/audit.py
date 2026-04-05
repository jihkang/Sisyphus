from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .config import TaskflowConfig
from .planning import collect_plan_gates
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
}

TRANSIENT_GATE_SOURCES = {
    "verify",
    "docs",
    "strategy",
    "close",
    "plan",
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


def run_verify(repo_root: Path, config: TaskflowConfig, task_id: str) -> VerifyOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent
    task = sync_test_strategy_from_docs(task=task, task_dir=task_dir)

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
    plan_gates = collect_plan_gates(task, action="verify")
    gates.extend(plan_gates)

    command_results: list[dict] = []
    if not spec_gates and not plan_gates:
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
    elif spec_gates:
        task["stage"] = "spec"
    elif plan_gates:
        task["stage"] = "plan_review"
    else:
        task["stage"] = "audit"

    verify_file = task_dir / task["docs"]["verify"]
    verify_file.write_text(_render_verify_markdown(task, command_results), encoding="utf-8")
    save_task_record(task_file=task_file, task=task)

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
    ]
    return any(marker in content for marker in placeholder_markers)
