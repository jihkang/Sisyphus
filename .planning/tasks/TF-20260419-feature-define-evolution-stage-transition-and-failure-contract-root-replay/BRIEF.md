# Brief

## Task

- Task ID: `TF-20260419-feature-define-evolution-stage-transition-and-failure-contract-root-replay`
- Type: `feature`
- Slug: `define-evolution-stage-transition-and-failure-contract-root-replay`
- Branch: `feat/define-evolution-stage-transition-and-failure-contract-root-replay`

## Problem

- `TF-20260418-feature-define-evolution-stage-transition-and-failure-contract` already defined and verified the stage/failure contract slice, but that task is blocked only because its stale task worktree predates the current root source-of-truth.
- The current root worktree now carries the active `taskflow` -> `sisyphus` migration baseline, so the stage machine must be replayed on top of that adopted baseline rather than resumed in the old worktree.
- This follow-up task must preserve the original narrow boundary: the minimum read-only stage model and stage-aware failure shape only.

## Desired Outcome

- The repository has an explicit read-only evolution run stage sequence with a documented path for later extension on top of the current root-adopted baseline.
- Each stage has a defined input, output, invariants, and failure shape.
- Failure reporting is stage-aware and reconstructable rather than opaque.

## Acceptance Criteria

- [ ] The initial read-only stages are defined and locked: `planned -> dataset_built -> harness_planned -> constraints_evaluated -> fitness_evaluated -> report_built -> failed`.
- [ ] The later extension path for `ready_for_review`, `followup_requested`, `promoted`, `invalidated`, and `rejected` is documented without being implemented.
- [ ] Each initial stage defines its input contract, output artifact, invariants, and failure shape.

## Constraints

- Keep scope to stage and failure contract definition only.
- Do not implement harness execution or Sisyphus follow-up behavior in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the stage model is too broad now, later slices will carry unused states and unclear semantics.
- If the stage model is too narrow, orchestration will have nowhere to record partial completion or failure provenance.
- If failure shape is under-specified, later code will collapse back to opaque exceptions.
