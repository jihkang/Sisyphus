# Brief

## Task

- Task ID: `TF-20260614-feature-add-test-first-loop-contract`
- Type: `feature`
- Slug: `add-test-first-loop-contract`
- Branch: `feat/add-test-first-loop-contract`

## Problem

- Add test-first loop contract evaluator
- Original request: Add a non-LLM, deterministic test-first loop contract evaluator for Sisyphus. The current eval loop only exposes test_first.status = todo. Implement a structured evaluator that can inspect recorded episode steps and determine whether test selection/generation happened before implementation, whether baseline tests ran before implementation, whether rerun tests happened after implementation, and whether evidence was recorded. Expose the result in eval loop JSON and through a CLI surface. Do not implement live test generation or model-driven test synthesis in this task; implement the harness-owned contract and validation surface first.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [x] Recorded episode steps can be evaluated for the test-first phase order.
- [x] Eval loop JSON exposes `test_first.status`, observed phases, missing phases, and violations.
- [x] CLI exposes a read-only test-first check for a task.
- [x] Missing or unannotated episodes produce a non-fabricated `not_recorded`/`incomplete` result.
- [x] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
