# Plan

## Implementation Plan

1. Add a normalized `design` bundle to task state so planning, spec freeze, verify, and conformance can read the same structure.
2. Extend `PLAN.md` / `FIX_PLAN.md` parsing to capture design depth, layer impact, required artifacts, and recorded artifacts.
3. Wire verify-time design assessment so underdesigned work reopens the existing plan/spec loop instead of remaining a passive note.
4. Update prompts, templates, fixtures, and targeted tests so new tasks see the protocol and existing flows stay compatible.

## Risks

- Reopening plan/spec from verify can interfere with existing plan-review and workflow transitions.
- Adding a new normalized state block can break projections or fixtures that assume only `test_strategy`.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `crosses a few modules`
- Confidence: `medium`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `planning, spec freeze, verify, and conformance now share a normalized design context`
- Required Design Artifacts: `boundary_note`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `docs/adaptive-planning-protocol.md`

## Test Strategy

### Normal Cases

- [x] Feature tasks persist and project the new `design` state without breaking existing task creation or prompts.
- [x] Spec freeze records a frozen design anchor that execution/conformance can reference later.

### Edge Cases

- [x] Old tasks without a filled design section still verify as `appropriate` instead of failing by default.
- [x] Underdesigned layer-changing plans reopen `plan_status/spec_status` through the existing review loop.

### Exception Cases

- [x] Missing required design artifacts surface actionable verify gates instead of silently drifting.

## Verification Mapping

- `Feature tasks persist and project the new design state without breaking existing task creation or prompts` -> `python -m unittest tests.test_sisyphus tests.test_golden`
- `Spec freeze records a frozen design anchor that execution/conformance can reference later` -> `python -m unittest tests.test_sisyphus`
- `Old tasks without a filled design section still verify as appropriate instead of failing by default` -> `python -m unittest tests.test_golden`
- `Underdesigned layer-changing plans reopen plan_status/spec_status through the existing review loop` -> `python -m unittest tests.test_sisyphus`
- `Missing required design artifacts surface actionable verify gates instead of silently drifting` -> `python -m unittest tests.test_sisyphus tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
