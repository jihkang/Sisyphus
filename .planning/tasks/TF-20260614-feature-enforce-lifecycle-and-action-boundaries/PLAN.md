# Plan

## Implementation Plan

1. Add a small lifecycle guard/helper layer that can be used by mutation handlers without creating import cycles.
2. Apply shared transition checks to plan revision, spec freeze, subtask generation, verify, promotion execution, and merged PR recording.
3. Preserve operator-gated plan approval/request changes/close behavior while making their lifecycle reasons visible through the same evaluator.
4. Update MCP mutation tools to return structured gate payloads instead of relying only on local exceptions where practical.
5. Add targeted regression tests for invalid and valid transition paths across planning, verify, promotion, and MCP surfaces.
6. Update task docs and run Sisyphus verify.

## Risks

- `planning.py` and `lifecycle_rules.py` can form circular imports if the evaluator is imported eagerly.
- Existing tests may rely on legacy idempotent operator behavior; this task should not over-tighten harmless repeat actions.
- Promotion code touches git/PR state; checks must run before expensive side effects.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `wires existing lifecycle/action abstractions into mutation paths without replacing the task storage model`
- Confidence: `medium`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `touches planning, audit, promotion, MCP, and tests while preserving existing public command shapes`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Valid plan approve -> spec freeze -> subtasks -> verify path still succeeds.
- [ ] Valid verified/promoted close path still succeeds.
- [ ] MCP mutation tools still return the same success payload shape for valid calls.

### Edge Cases

- [ ] Repeat/operator-gated actions do not become autonomous policy-safe actions.
- [ ] Existing local gates are deduped with lifecycle gates.
- [ ] Promotion resume path still works when a head SHA is already recorded.

### Exception Cases

- [ ] Plan revision without requested changes is blocked.
- [ ] Spec freeze without plan approval is blocked by lifecycle gates.
- [ ] Subtask generation without frozen spec is blocked by lifecycle gates.
- [ ] Verify before plan/spec readiness is blocked before audit side effects.
- [ ] Promotion before verify pass is blocked before git side effects.

## Verification Mapping

- `Valid and invalid lifecycle rules` -> `.venv/bin/python -m unittest tests.test_lifecycle_rules -v`
- `Planning/verify/promotion integration` -> `.venv/bin/python -m unittest tests.test_sisyphus -v`
- `MCP mutation tool behavior` -> `.venv/bin/python -m unittest tests.test_mcp_core -v`
- `Full regression suite` -> `.venv/bin/python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
