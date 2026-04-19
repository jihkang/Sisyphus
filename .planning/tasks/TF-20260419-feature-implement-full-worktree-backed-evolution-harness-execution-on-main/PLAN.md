# Plan

## Implementation Plan

1. Inspect the current evolution execution boundary and isolate the remaining worktree-backed gap.
   - Confirm what `execute_sisyphus_evaluation(...)` already does today: task creation, plan approval, spec freeze, materialization, and optional provider-wrapper launch.
   - Confirm what is still missing: concrete command planning, direct command execution in the isolated evaluation worktree, structured receipts, and metrics derived from real command results.
2. Introduce command-plan and receipt models for worktree-backed harness execution.
   - Add the minimum structures/constants needed to describe execution mode, normalized commands, command results, and receipt locations.
   - Keep the models scoped to evaluation evidence and do not widen them into promotion or follow-up execution contracts.
3. Implement the isolated worktree-backed executor.
   - Reuse the bounded isolated evaluation task/worktree setup.
   - Derive a command plan from available evaluation inputs such as selected-task verify history and/or declared verify commands.
   - Normalize commands so they execute against the isolated evaluation worktree rather than historical source paths.
   - Run the commands inside the evaluation worktree, capture stdout/stderr/runtime/exit code, and persist a structured receipt under the evaluation task artifact area.
4. Connect receipts back into evaluation metrics and evidence.
   - Compute verify-pass information from executed commands when receipts exist.
   - Expose receipt paths and command counts through `EvolutionEvaluationEvidence`.
   - Preserve the existing failure semantics so command failures produce blocked/failed evaluation outcomes with actionable evidence.
5. Keep the authority boundary intact.
   - Do not add production follow-up bridge logic.
   - Do not add promotion/invalidation recording.
   - Do not add CLI/MCP evolution ingress.
6. Add focused tests and update task docs.
   - Cover successful baseline/candidate worktree-backed execution.
   - Cover command normalization and receipt persistence.
   - Cover failed command execution and missing-command-plan behavior without live repo mutation.

## Risks

- Historical verify commands may contain absolute worktree paths or shell wrappers that need normalization before they can run inside a fresh isolated evaluation worktree.
- If the executor mutates live repo state outside the isolated evaluation task/worktree, it breaks the evolution safety boundary.
- If receipt capture is too weak, constraints and fitness will continue to rely on synthetic metrics instead of reconstructable execution evidence.

## Test Strategy

### Normal Cases

- [x] A worktree-backed baseline/candidate evaluation can execute a normalized command plan and persist structured receipts.
- [x] Executed command results feed `EvolutionEvaluationEvidence` and runtime-aware metrics instead of summary-only placeholders.

### Edge Cases

- [x] Commands that include historical `cd <old-worktree> && ...` prefixes are normalized to the isolated evaluation worktree correctly.
- [x] Duplicate commands across selected task traces are de-duplicated in a stable order while still producing deterministic receipts.

### Exception Cases

- [x] A failed command produces a failed evaluation outcome with receipt metadata and actionable evidence.
- [x] Missing executable command inputs fail loudly without mutating the live repository or widening into production follow-up logic.

## Verification Mapping

- `A worktree-backed baseline/candidate evaluation can execute a normalized command plan and persist structured receipts.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Executed command results feed EvolutionEvaluationEvidence and runtime-aware metrics instead of summary-only placeholders.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Commands that include historical cd <old-worktree> && ... prefixes are normalized to the isolated evaluation worktree correctly.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Duplicate commands across selected task traces are de-duplicated in a stable order while still producing deterministic receipts.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A failed command produces a failed evaluation outcome with receipt metadata and actionable evidence.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Missing executable command inputs fail loudly without mutating the live repository or widening into production follow-up logic.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
