# Plan

## Implementation Plan

1. Extend `src/taskflow/evolution/runner.py` from a plan-only model into a stage-aware orchestration layer.
   - Add explicit run lifecycle states such as `planned`, `dataset_ready`, `harness_executed`, `evaluated`, `reported`, and `failed`.
   - Define a stable run result model that can carry the planned run, built dataset, executed harness, constraint result, fitness result, report, current stage, and failure metadata.
2. Add a single orchestration entrypoint for automatic progression.
   - Introduce an `execute_evolution_run(...)` style function that composes `plan_evolution_run`, `build_evolution_dataset`, `execute_evolution_harness`, `evaluate_evolution_constraints`, `evaluate_evolution_fitness`, and `build_evolution_report`.
   - Keep the entrypoint operator-invoked and synchronous in the first slice; do not add background scheduling yet.
3. Replace the generic post-evaluation callback with a Sisyphus-managed follow-up execution request.
   - Model a follow-up request shape that carries the task message, instruction, provider, ownership, and source context for isolated self-hosted execution.
   - Route automatic follow-up execution through Sisyphus task creation plus plan approval, spec freeze, and provider-wrapper launch in an isolated task worktree only after hard guards pass and promotion eligibility is explicit.
4. Define controlled inputs and injection points instead of hard-coding policy.
   - Accept explicit `task_ids` and `target_ids` scope.
   - Accept hard-guard inputs such as warning threshold, MCP compatibility result, and output contract stability result.
   - Accept an injectable harness evaluation executor so tests and later candidate evaluators can plug in without changing the runner contract.
5. Make failure handling stage-aware and inspectable.
   - If dataset build, harness execution, or downstream evaluation fails, capture the failing stage and partial artifacts rather than crashing without context.
   - Preserve the isolation contract: failures should still leave the live repository worktree untouched.
   - If Sisyphus follow-up task creation, approval, freeze, or execution fails, capture the failing stage and task metadata rather than collapsing into an opaque callback error.
6. Cover the orchestration path with focused tests.
   - Happy path: the runner returns a reported result with populated dataset, harness, constraints, fitness, report, and a launched Sisyphus follow-up task when requested.
   - Edge path: narrowed task/target scope and injected harness checks flow through correctly while follow-up stays opt-in.
   - Failure path: follow-up task creation or execution failures return a failed run result with the correct stage and partial results.
7. Defer MCP evolution surface and approval-driven promotion flows to the next slice.
   - Once the orchestration and follow-up request models are stable, use them as the backing shape for `evolution_status`, `evolution_compare`, evolution report resources, and later approval-driven branch or PR materialization.

## Risks

- If the runner result model is too narrow now, later MCP and approval flows will need avoidable churn.
- If guard inputs are buried inside the runner instead of injected, future compatibility checks will be hard to extend.
- If the runner mutates the live repository worktree during automation, it will violate the isolation guarantees already documented for evolution work.
- If self-hosted follow-up bypasses Sisyphus task lifecycle steps, execution and audit evidence will fragment across two control paths.

## Test Strategy

### Normal Cases

- [ ] An automated evolution run can progress from run planning through report generation and guarded Sisyphus follow-up launch in one call.

### Edge Cases

- [ ] Narrowed task or target scope still produces a stable reported result when follow-up execution is not requested.

### Exception Cases

- [ ] A stage failure returns actionable failure metadata without mutating the live repository worktree.

## Verification Mapping

- `An automated evolution run can progress from run planning through report generation and guarded Sisyphus follow-up launch in one call.` -> `uv run python -m unittest tests.test_evolution -v`
- `Narrowed task or target scope still produces a stable reported result when follow-up execution is not requested.` -> `targeted regression test`
- `A stage failure returns actionable failure metadata without mutating the live repository worktree.` -> `targeted regression test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
