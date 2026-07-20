from __future__ import annotations

from ..domain.task.design import DESIGN_MODE_NONE, ensure_task_design_defaults
from ..domain.verification import CommandExecution, VerificationStatus
from .ports.workflow import TaskRecord


def render_verify_markdown(
    task: TaskRecord,
    command_results: tuple[CommandExecution, ...],
) -> str:
    passed = task["verify_status"] == VerificationStatus.PASSED.value
    result_line = "go next task" if passed else "return to current task"
    strategy = task.get("test_strategy", {})
    external_llm = strategy.get("external_llm", {})
    ensure_task_design_defaults(task)
    design = task.get("design", {})
    assessment = design.get("assessment", {})
    missing_artifacts = list(assessment.get("missing_artifacts") or [])
    spec_validation = (
        task.get("spec_validation")
        if isinstance(task.get("spec_validation"), dict)
        else {}
    )
    command_lines = (
        [f"- `{result.command}` -> `{result.status.value}`" for result in command_results]
        if command_results
        else ["- No verify commands configured"]
    )
    gate_lines = [
        f"- `{gate['code']}`: {gate['message']}" for gate in task.get("gates", [])
    ] or ["- None"]
    spec_validation_lines: list[str] = []
    if spec_validation:
        spec_validation_lines = [
            "## Spec Validation",
            "",
            f"- Status: `{spec_validation.get('status', 'missing')}`",
            f"- Stale: `{'yes' if spec_validation.get('stale') else 'no'}`",
            f"- Report: `{spec_validation.get('report_path', 'not_recorded')}`",
            "",
        ]
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
            *spec_validation_lines,
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


def looks_like_unfilled_template(content: str) -> bool:
    if not content:
        return True
    markers = [
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
    return any(marker in content for marker in markers)


__all__ = ["looks_like_unfilled_template", "render_verify_markdown"]
