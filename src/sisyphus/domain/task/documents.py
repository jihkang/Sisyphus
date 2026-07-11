from __future__ import annotations


def render_brief(
    task: dict,
    title: str,
    message: str,
    *,
    requested_slug: str,
    parent_task_id: str | None,
) -> str:
    lines = [
        "# Brief",
        "",
        "## Task",
        "",
        f"- Task ID: `{task['id']}`",
        f"- Type: `{task['type']}`",
        f"- Slug: `{task['slug']}`",
        f"- Branch: `{task['branch']}`",
    ]
    if requested_slug and requested_slug != str(task["slug"]):
        lines.append(f"- Requested Slug: `{requested_slug}`")
    if parent_task_id:
        lines.append(f"- Follow-up Of: `{parent_task_id}`")
    lines.extend(
        [
            "",
            "## Problem" if task["type"] == "feature" else "## Symptom",
            "",
            f"- {title}",
            f"- Original request: {message}",
        ]
    )
    if parent_task_id:
        lines.append(f"- This task continues implementation work after `{parent_task_id}` was closed.")
    lines.extend(
        [
            "",
            "## Desired Outcome" if task["type"] == "feature" else "## Expected Behavior",
            "",
            "- The repository behavior matches the requested conversation outcome.",
            "- The resulting change stays scoped to this task branch and worktree.",
            "",
            "## Acceptance Criteria" if task["type"] == "feature" else "## Impact",
            "",
            "- [ ] The requested workflow is implemented or corrected.",
            "- [ ] The task docs reflect the actual implementation and verification scope.",
            "- [ ] Verification notes are ready to be updated after implementation.",
            "",
            "## Constraints" if task["type"] == "feature" else "## Notes",
            "",
            "- Preserve existing repository conventions unless the task requires a deliberate change.",
            "- Re-read the task docs before verify and close.",
            "",
        ]
    )
    return "\n".join(lines)


def render_feature_plan(task: dict, title: str, message: str) -> str:
    _ = task
    request_summary = single_line(message)
    return "\n".join(
        [
            "# Plan",
            "",
            "## Implementation Plan",
            "",
            f"1. Inspect the current code path related to: {title}.",
            f"2. Implement the requested behavior for: {request_summary}.",
            "3. Update tests and task docs to match the final behavior.",
            "",
            "## Risks",
            "",
            "- The conversation request may omit edge conditions that still matter in the current codebase.",
            "- The change may affect adjacent flows if the requested behavior touches shared state.",
            "",
            "## Design Evaluation",
            "",
            "- Design Mode: `none`",
            "- Decision Reason: `existing contract only`",
            "- Confidence: `medium`",
            "- Layer Impact: `layer-preserving`",
            "- Layer Decision Reason: `n/a`",
            "- Required Design Artifacts: `none`",
            "",
            "## Design Artifacts",
            "",
            "- Connection Diagram: `n/a`",
            "- Sequence Diagram: `n/a`",
            "- Boundary Note: `n/a`",
            "",
            "## Test Strategy",
            "",
            "### Normal Cases",
            "",
            "- [ ] Requested conversation workflow succeeds",
            "",
            "### Edge Cases",
            "",
            "- [ ] Minimal valid input still behaves predictably",
            "",
            "### Exception Cases",
            "",
            "- [ ] Unexpected failure surfaces an actionable error",
            "",
            "## Verification Mapping",
            "",
            "- `Requested conversation workflow succeeds` -> `sisyphus verify`",
            "- `Minimal valid input still behaves predictably` -> `targeted regression test`",
            "- `Unexpected failure surfaces an actionable error` -> `manual review`",
            "",
            "## External LLM Review",
            "",
            "- Required: `no`",
            "- Provider: `n/a`",
            "- Purpose: `n/a`",
            "- Trigger: `n/a`",
            "",
        ]
    )


def render_issue_repro(task: dict, title: str, message: str) -> str:
    _ = task
    return "\n".join(
        [
            "# Repro",
            "",
            "## Preconditions",
            "",
            "- Repository is checked out in the task worktree.",
            "- The current branch reproduces the reported behavior.",
            "",
            "## Repro Steps",
            "",
            f"1. Follow the workflow described by the request: {title}.",
            "2. Observe the current incorrect behavior in the relevant code path.",
            "3. Compare the observed result against the expected result below.",
            "",
            "## Observed Result",
            "",
            f"- {message}",
            "",
            "## Expected Result",
            "",
            "- The reported issue no longer occurs once the fix is applied.",
            "",
            "## Regression Test Target",
            "",
            "- Add or update a regression-oriented test that fails before the fix and passes after it.",
            "",
        ]
    )


def render_issue_fix_plan(task: dict, title: str, message: str) -> str:
    _ = task
    request_summary = single_line(message)
    return "\n".join(
        [
            "# Fix Plan",
            "",
            "## Root Cause Hypothesis",
            "",
            f"- The behavior described by the request likely originates in the code path for: {title}.",
            "",
            "## Fix Strategy",
            "",
            f"1. Confirm the failing path described by: {request_summary}.",
            "2. Add or update a regression test around the failing path.",
            "3. Implement the fix and re-run the relevant checks.",
            "4. Update task docs with the verified outcome.",
            "",
            "## Design Evaluation",
            "",
            "- Design Mode: `none`",
            "- Decision Reason: `existing contract only`",
            "- Confidence: `medium`",
            "- Layer Impact: `layer-preserving`",
            "- Layer Decision Reason: `n/a`",
            "- Required Design Artifacts: `none`",
            "",
            "## Design Artifacts",
            "",
            "- Connection Diagram: `n/a`",
            "- Sequence Diagram: `n/a`",
            "- Boundary Note: `n/a`",
            "",
            "## Test Strategy",
            "",
            "### Normal Cases",
            "",
            "- [ ] Regression scenario now passes",
            "",
            "### Edge Cases",
            "",
            "- [ ] Neighboring behavior remains stable",
            "",
            "### Exception Cases",
            "",
            "- [ ] Invalid or missing input still fails safely",
            "",
            "## Verification Mapping",
            "",
            "- `Regression scenario now passes` -> `sisyphus verify`",
            "- `Neighboring behavior remains stable` -> `targeted regression test`",
            "- `Invalid or missing input still fails safely` -> `manual review`",
            "",
            "## External LLM Review",
            "",
            "- Required: `no`",
            "- Provider: `n/a`",
            "- Purpose: `n/a`",
            "- Trigger: `n/a`",
            "",
        ]
    )


def single_line(value: str) -> str:
    collapsed = " ".join(part.strip() for part in value.splitlines() if part.strip())
    return collapsed or "No details provided"


__all__ = [
    "render_brief",
    "render_feature_plan",
    "render_issue_fix_plan",
    "render_issue_repro",
    "single_line",
]
