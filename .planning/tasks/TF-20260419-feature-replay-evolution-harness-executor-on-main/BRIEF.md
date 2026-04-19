# Brief

## Task

- Task ID: `TF-20260419-feature-replay-evolution-harness-executor-on-main`
- Type: `feature`
- Slug: `replay-evolution-harness-executor-on-main`
- Branch: `feat/replay-evolution-harness-executor-on-main`

## Problem

- The previously closed harness-executor slice did not land on the current `main` baseline. The current `src/sisyphus/evolution/harness.py` still stops at planning-only harness output.
- The current code lacks:
  - executed baseline/candidate evaluation outcomes
  - evaluation evidence models for isolated runs
  - a bounded Sisyphus-backed evaluation request/executor path
  - a summary fallback executor that converts dataset traces into completed metrics without mutating repo state
- This gap means the evolution loop can plan and score placeholders, but it cannot yet execute an actual isolated evaluation step on the current baseline.

## Desired Outcome

- `src/sisyphus/evolution/harness.py` supports an execution layer on top of the existing harness plan.
- The new execution layer can:
  - populate completed evaluation metrics through a summary fallback path
  - capture isolated evaluation evidence through a bounded Sisyphus-backed path
  - preserve live repo and live task-state isolation
- The slice stays evaluation-only. It must not introduce production follow-up execution, promotion, or MCP/CLI surface changes.

## Acceptance Criteria

- [ ] `EvolutionEvaluationEvidence`, `EvolutionEvaluationOutcome`, and related execution constants exist in `sisyphus.evolution.harness`.
- [ ] `execute_evolution_harness(...)` executes baseline and candidate evaluations and returns a populated `EvolutionHarnessPlan` with completed or failed evaluation states.
- [ ] `summarize_dataset_evaluation(...)` provides a deterministic fallback executor that derives metrics from dataset traces without mutating repository files.
- [ ] A bounded `build_sisyphus_evaluation_request(...)` and `execute_sisyphus_evaluation(...)` path exists for isolated evaluation tasks only.
- [ ] The slice does not add production follow-up execution, promotion recording, or MCP/CLI ingress.
- [ ] Task docs and verification notes reflect the final implementation and test scope.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to evaluation-only harness execution.
- Do not add evolution follow-up bridge logic for production changes in this task.
- Do not let this slice widen into promotion, invalidation, or MCP/CLI ingress.
- Re-read the task docs before verify and close.
