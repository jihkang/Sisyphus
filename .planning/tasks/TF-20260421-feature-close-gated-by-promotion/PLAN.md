# Plan

## Implementation Plan

1. Extend closeout gating so verified tasks with `promotion.required=true` only close when promotion is in a terminal recorded state.
2. When promotion is still pending, leave the task in an explicit `promotion_pending` workflow phase and `promotion` stage rather than collapsing everything into a generic blocked/audit state.
3. Update workflow auto-loop logic so it recognizes `promotion_pending` as a parked state and does not keep re-running verify/close cycles.
4. Add focused regressions for closeout behavior and broader regressions to confirm the new phase does not disturb adjacent MCP/evolution flows.

## Risks

- Closeout now depends on promotion state, so bad gating could strand tasks that should still close.
- Workflow auto-loop needs to stop cleanly on `promotion_pending`; otherwise the daemon can churn on already-verified tasks.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `touches closeout and workflow state transitions across an existing boundary but does not add a new layer`
- Confidence: `high`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `the task redefines how verified work transitions into promotion waiting states`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `closeout now consults the first-class promotion bundle before final closure`

## Test Strategy

### Normal Cases

- [x] Verified tasks with promotion still pending remain open in `promotion_pending` instead of closing.
- [x] Verified tasks whose promotion is `promotion_recorded` still close successfully.

### Edge Cases

- [x] Workflow auto-loop does not reprocess tasks already parked in `promotion_pending`.
- [x] Existing closeout behavior for non-promotable verified tasks still works.

### Exception Cases

- [x] Closeout still surfaces explicit close gates when verification is missing or promotion is incomplete.

## Verification Mapping

- `Verified tasks with promotion still pending remain open in promotion_pending instead of closing` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Verified tasks whose promotion is promotion_recorded still close successfully` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Workflow auto-loop does not reprocess tasks already parked in promotion_pending` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Existing closeout behavior for non-promotable verified tasks still works` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Closeout still surfaces explicit close gates when verification is missing or promotion is incomplete` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Shared workflow, MCP, evolution, and golden-template paths stay stable after the close gate change` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_server tests.test_mcp_core tests.test_mcp_adapter tests.test_evolution tests.test_golden`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
