# Brief

## Task

- Task ID: `TF-20260418-feature-implement-execute-evolution-run-read-only-orchestrator`
- Type: `feature`
- Slug: `implement-execute-evolution-run-read-only-orchestrator`
- Branch: `feat/implement-execute-evolution-run-read-only-orchestrator`

## Problem

- The current evolution package still stops at separately called helper functions and has no single entrypoint that closes the read-only flow.
- Without one read-only orchestrator, later executor and bridge tasks will be built on an unstable, manually stitched sequence.
- This task must add the first orchestration entrypoint while preserving the no-live-mutation boundary.

## Desired Outcome

- The repository has an `execute_evolution_run(...)` path that composes run planning, dataset build, harness planning, constraints, fitness, reporting, and append-only run-artifact persistence.
- The orchestrator writes only under `.planning/evolution/runs/<run_id>/`.
- Failures preserve stage-aware metadata and partial artifacts rather than crashing opaquely.

## Acceptance Criteria

- [ ] `execute_evolution_run(...)` composes `plan_evolution_run`, `build_evolution_dataset`, harness planning, constraints evaluation, fitness evaluation, report generation, and append-only artifact persistence.
- [ ] The run stores append-only artifacts such as `run.json`, `dataset.json`, `harness_plan.json`, `constraints.json`, `fitness.json`, and `report.md` under `.planning/evolution/runs/<run_id>/`.
- [ ] The orchestrator does not mutate `src/`, `templates/`, provider configuration, or `.planning/tasks/<live_task_id>/`.
- [ ] On failure, the run persists stage-aware failure metadata with enough detail to identify the stopping point.

## Constraints

- Keep scope to the read-only orchestration closure over the existing evolution modules.
- Do not call `provider_wrapper`, trigger promotion, or create follow-up tasks in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the orchestrator mutates live repo or task state, it will violate the boundary needed for later self-hosted execution.
- If append-only artifact persistence is not explicit, later runs will be hard to inspect and harder to reconstruct.
- If failures do not persist stage-aware metadata, operator review will still be forced to infer the stopping point from logs.
