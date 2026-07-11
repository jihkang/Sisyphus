# Brief

## Task

- Task ID: `TF-20260614-feature-enforce-lifecycle-and-action-boundaries`
- Type: `feature`
- Slug: `enforce-lifecycle-and-action-boundaries`
- Branch: `feat/enforce-lifecycle-and-action-boundaries`

## Problem

- The previous foundation task added lifecycle rules, action risk metadata, and observation rendering.
- The rules are only partially enforced by mutation paths; closeout uses them, but planning, verify, subtask, promotion, and MCP mutation surfaces still rely on local checks.
- Sisyphus should expose the same lifecycle decision across CLI and MCP surfaces so invalid transitions cannot bypass the harness.

## Desired Outcome

- State-mutating operations consult the shared lifecycle transition evaluator before applying changes.
- Forbidden transitions persist structured gates and return actionable reasons.
- Human/review-gated actions remain available to operators but are not classified as policy-safe autonomous actions.
- Existing valid workflows continue to pass.

## Acceptance Criteria

- [ ] Plan revision is blocked unless plan changes were requested.
- [ ] Spec freeze is blocked until plan approval by the shared lifecycle evaluator.
- [ ] Subtask generation is blocked until plan/spec readiness by the shared lifecycle evaluator.
- [ ] Verify is blocked by lifecycle gates before audit mutation.
- [ ] Promotion execution is blocked unless verify/conformance/spec readiness passes.
- [ ] Merged PR recording is blocked for closed tasks and invalid task/branch matches still fail loudly.
- [ ] MCP mutation tools and direct Python/CLI paths report the same lifecycle gates for invalid transitions.
- [ ] Existing valid lifecycle, promotion, MCP, and verification tests still pass.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
