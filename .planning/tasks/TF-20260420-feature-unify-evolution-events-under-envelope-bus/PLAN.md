# Plan

## Implementation Plan

1. Inspect current repository event-bus helpers and evolution entry points to identify the minimal emission points.
2. Define a narrow evolution event vocabulary and shared publisher helper so event payloads stay consistent across slices.
3. Emit envelope-bus events from read-only run orchestration, follow-up bridge, receipt projection, verification projection, and decision-envelope recording.
4. Add focused tests that assert event payloads and lineage fields without broadening into CLI/MCP surface work.
5. Update task docs and verification notes to match the final event-emission scope.

## Risks

- If event publishing is added to low-level pure helpers instead of repo-aware entry points, callers may get duplicate or context-free events.
- If payloads omit run/candidate/task lineage, the event stream will still be too weak for downstream automation.
- If this slice drifts into new surface APIs or orchestration logic, it will blur the boundary between observability and control.

## Test Strategy

### Normal Cases

- [ ] `execute_evolution_run` writes `evolution.run.recorded` for a successful read-only run.
- [ ] `bridge_evolution_followup_request` writes `evolution.followup.requested` with run/candidate/task lineage.

### Edge Cases

- [ ] `project_followup_execution` and `project_followup_verification` write projection events with receipt/verification counts and stable lineage.
- [ ] `record_evolution_decision_envelope` writes `evolution.decision.recorded` with promotion vs invalidation status preserved in the event payload.

### Exception Cases

- [ ] A failing `execute_evolution_run` writes `evolution.run.failed` with failure stage and persisted artifact context.

## Verification Mapping

- `execute_evolution_run writes evolution.run.recorded for a successful read-only run.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `bridge_evolution_followup_request writes evolution.followup.requested with run/candidate/task lineage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `project_followup_execution and project_followup_verification write projection events with stable lineage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `record_evolution_decision_envelope writes evolution.decision.recorded with promotion vs invalidation preserved.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A failing execute_evolution_run writes evolution.run.failed with failure context.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
