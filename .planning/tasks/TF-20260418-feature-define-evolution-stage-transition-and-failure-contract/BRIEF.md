# Brief

## Task

- Task ID: `TF-20260418-feature-define-evolution-stage-transition-and-failure-contract`
- Type: `feature`
- Slug: `define-evolution-stage-transition-and-failure-contract`
- Branch: `feat/define-evolution-stage-transition-and-failure-contract`

## Problem

- The evolution foundation still lacks one explicit stage machine that says how a run progresses and how partial failures are represented.
- Without a stable stage-transition and failure contract, orchestration code will either crash opaquely or invent ad hoc intermediate states that cannot be reconstructed later.
- This task must define the minimum read-only stage model and the failure shape for the next orchestration slice.

## Desired Outcome

- The repository has an explicit read-only evolution run stage sequence with a documented path for later extension.
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
