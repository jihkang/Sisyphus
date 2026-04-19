# Brief

## Task

- Task ID: `TF-20260419-feature-replay-evolution-candidate-materialization-on-main`
- Type: `feature`
- Slug: `replay-evolution-candidate-materialization-on-main`
- Branch: `feat/replay-evolution-candidate-materialization-on-main`

## Problem

- The previously closed candidate-materialization slice did not land on the current `main` baseline.
- The current evolution control plane can now plan harness evaluations and execute evaluation-only harness runs, but it still lacks a materialization layer that prepares isolated baseline/candidate snapshots for those runs.
- Without candidate materialization, the harness executor cannot advance from dataset-summary evaluation toward branch/worktree-backed evaluation inputs.
- This task must stay strictly evaluation-only. It must not add production follow-up execution, promotion/invalidation writes, or MCP/CLI ingress.

## Desired Outcome

- `src/sisyphus/evolution` gains a bounded candidate-materialization layer for isolated harness runs.
- The materialization layer can prepare baseline/candidate snapshot descriptors and file-system isolation metadata without mutating the live repository or live task state.
- The output integrates with the existing harness execution slice but remains separate from production follow-up execution.

## Acceptance Criteria

- [x] A candidate-materialization contract exists in `sisyphus.evolution` for baseline/candidate evaluation inputs.
- [x] Materialization produces isolated snapshot/workspace metadata suitable for evaluation-only harness runs.
- [x] Live repo mutation and live task-state mutation remain explicitly disallowed in this slice.
- [x] The task docs reflect the actual implementation and verification scope.
- [x] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to isolated evaluation candidate materialization only.
- Do not add production follow-up bridge logic, promotion/invalidation recording, or MCP/CLI ingress.
- Re-read the task docs before verify and close.
