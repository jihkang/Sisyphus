# Plan

## Implementation Plan

1. Inspect the current `sisyphus.evolution` surface and isolate the materialization gap.
   - Confirm what the current harness executor can already do.
   - Confirm what snapshot/workspace metadata is still missing before full worktree-backed evaluation.
2. Port the missing candidate-materialization concepts onto the current `sisyphus` namespace.
   - Add the minimum data model for isolated baseline/candidate materialization inputs and outputs.
   - Keep the contract evaluation-only and explicitly separate from follow-up execution or promotion.
3. Implement bounded materialization helpers.
   - Prepare isolated baseline/candidate snapshot descriptors.
   - Capture workspace location, target scope, and materialization notes without mutating live repo state.
   - Keep the output suitable for the existing harness execution layer.
4. Keep the current evolution authority boundary intact.
   - Do not add production follow-up bridge logic.
   - Do not add promotion/invalidation writes.
   - Do not add MCP/CLI ingress here.
5. Add focused tests and update task docs.
   - Cover normal materialization output.
   - Cover narrowed candidate scope and isolation metadata.
   - Cover failure behavior without live repo mutation.

## Risks

- The old slice lived in the `taskflow` namespace, so replaying it blindly could regress the current `sisyphus.evolution` contracts.
- If the materialization layer writes into the live repo or live task state, it breaks the evolution safety boundary.
- If materialization is conflated with the future production follow-up bridge, the authority boundary will blur again.

## Test Strategy

### Normal Cases

- [x] Baseline/candidate materialization returns bounded isolation metadata suitable for evaluation-only harness runs.

### Edge Cases

- [x] Narrowed candidate scope preserves run ordering and target ownership in the materialized output.

### Exception Cases

- [x] Materialization failures surface actionable errors without mutating live repo state or task state.

## Verification Mapping

- `Baseline/candidate materialization returns bounded isolation metadata suitable for evaluation-only harness runs.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Narrowed candidate scope preserves run ordering and target ownership in the materialized output.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Materialization failures surface actionable errors without mutating live repo state or task state.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
