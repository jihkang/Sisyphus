# Plan

## Implementation Plan

1. Inspect the current `sisyphus.evolution` surface and isolate the execution gap.
   - Confirm that `harness.py` is still planning-only.
   - Confirm that current `orchestrator.py` remains read-only by default and should not be broadened into production follow-up behavior in this slice.
2. Port the missing harness-executor concepts onto the current `sisyphus` namespace.
   - Add execution status constants and execution-mode constants.
   - Add `EvolutionEvaluationEvidence` and `EvolutionEvaluationOutcome`.
   - Extend `EvolutionEvaluationPlan` to carry optional evidence.
3. Implement bounded harness execution helpers.
   - Add `summarize_dataset_evaluation(...)` as the deterministic fallback executor from dataset traces.
   - Add `execute_evolution_harness(...)` to execute baseline/candidate and return completed or failed evaluation states.
   - Preserve live repo immutability and explicit failure metadata.
4. Add the isolated Sisyphus evaluation request path.
   - Add `build_sisyphus_evaluation_request(...)`.
   - Add `execute_sisyphus_evaluation(...)` for isolated evaluation tasks only.
   - Keep any task creation/approval/spec-freeze inside the evaluation-only request path and do not reuse it for production follow-up execution.
5. Keep the current orchestrator boundary intact.
   - If `orchestrator.execute_evolution_run(...)` is touched, keep its default behavior compatible with the existing read-only contract.
   - Do not add auto-follow-up, promotion, or MCP/CLI ingress here.
6. Add focused tests and update task docs.
   - Cover summary fallback execution.
   - Cover bounded Sisyphus-backed evaluation evidence.
   - Cover failed evaluation outcomes without live repo mutation.

## Risks

- The previously closed task carried older `taskflow`-namespace code, so replaying it blindly could regress the current `sisyphus.evolution` contract and read-only orchestrator tests.
- If the execution layer mutates live task state or writes outside isolated evaluation context, it breaks the evolution safety boundary.
- If the Sisyphus-backed evaluation helper is conflated with the future production follow-up bridge, the no-self-approval boundary will blur again.

## Test Strategy

### Normal Cases

- [ ] `execute_evolution_harness(...)` can populate completed baseline/candidate metrics through the summary fallback path.
- [ ] A bounded Sisyphus-backed evaluation request can return captured evidence and completed evaluation status.

### Edge Cases

- [ ] Narrowed candidate target scope preserves run-order semantics while still executing through the harness.
- [ ] Optional orchestrator integration, if added, keeps the existing read-only default behavior stable.

### Exception Cases

- [ ] Failed evaluation executors surface actionable failure metadata and do not mutate repository files.
- [ ] Sisyphus-backed evaluation launch failures keep evidence when available and mark the evaluation as failed rather than silently succeeding.

## Verification Mapping

- `execute_evolution_harness(...) can populate completed baseline/candidate metrics through the summary fallback path.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A bounded Sisyphus-backed evaluation request can return captured evidence and completed evaluation status.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Narrowed candidate target scope preserves run-order semantics while still executing through the harness.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Optional orchestrator integration, if added, keeps the existing read-only default behavior stable.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Failed evaluation executors surface actionable failure metadata and do not mutate repository files.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Sisyphus-backed evaluation launch failures keep evidence when available and mark the evaluation as failed rather than silently succeeding.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
