# Plan

## Implementation Plan

1. Audit the current evolution implementation on `main` and confirm the requested slice is already present in the materialization, worktree-backed harness execution, and read-only orchestration paths.
2. Align this task's docs with reality instead of reimplementing the same slice: record the concrete modules, command paths, and regression tests that satisfy the request.
3. Verify the existing implementation with targeted evolution tests, then close this task as satisfied-on-main and hand off to the next unimplemented slice.

## Risks

- This task was created after the slice had already landed on `main`, so the main risk is duplicate work or an incorrect reopen of finished scope.
- `runner.py` still contains stale plan-only notes even though orchestration and worktree-backed execution exist elsewhere; the audit must distinguish documentation drift from missing executor behavior.
- Verification must prove isolation boundaries clearly: live repo state cannot be mutated outside `.planning/evolution/runs/<run_id>/` and the dedicated evaluation worktree.

## Test Strategy

### Normal Cases

- [ ] `execute_worktree_backed_evaluation` materializes candidate state into an isolated evaluation worktree, executes normalized verify commands, and persists execution receipts plus evidence paths.
- [ ] `execute_evolution_run` persists `run.json`, `dataset.json`, `harness_plan.json`, `constraints.json`, `fitness.json`, and `report.md` under `.planning/evolution/runs/<run_id>/`.

### Edge Cases

- [ ] Worktree command planning strips stale `cd <old worktree> && ...` prefixes and dedupes repeated inherited verify commands before execution.
- [ ] Read-only orchestration preserves the live repo snapshot while writing only append-only run artifacts under `.planning/evolution/runs/<run_id>/`.

### Exception Cases

- [ ] Missing rewrite anchors or command failures raise `EvolutionEvaluationExecutionError` with actionable evidence, including materialization status or execution receipt paths.

## Verification Mapping

- `execute_worktree_backed_evaluation materializes candidate state into an isolated evaluation worktree, executes normalized verify commands, and persists execution receipts plus evidence paths.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `execute_evolution_run persists run.json, dataset.json, harness_plan.json, constraints.json, fitness.json, and report.md under .planning/evolution/runs/<run_id>/.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Worktree command planning strips stale cd <old worktree> && ... prefixes and dedupes repeated inherited verify commands before execution.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Read-only orchestration preserves the live repo snapshot while writing only append-only run artifacts under .planning/evolution/runs/<run_id>/.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Missing rewrite anchors or command failures raise EvolutionEvaluationExecutionError with actionable evidence, including materialization status or execution receipt paths.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
