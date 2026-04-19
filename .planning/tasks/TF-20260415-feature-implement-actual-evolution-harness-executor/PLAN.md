# Plan

## Implementation Plan

1. Align the task worktree to the current local evolution foundation.
   - The repository `main` worktree was still behind the local evolution package baseline.
   - Fast-forward the task worktree to the current local evolution foundation before implementing the harness executor slice.
2. Restore the stage-aware evolution orchestration baseline in this task branch.
   - Bring in the stage-aware `runner.py` orchestration and guarded Sisyphus follow-up execution support that the harness executor will build on.
3. Extend `src/taskflow/evolution/harness.py` with an actual Sisyphus-backed evaluation executor shape.
   - Add explicit evaluation evidence and request models for isolated evaluation tasks/worktrees.
   - Add a bounded `execute_sisyphus_evaluation(...)` path that creates isolated Sisyphus evaluation tasks, approves and freezes them, optionally launches provider execution, and returns metrics plus evidence.
   - Keep `summarize_dataset_evaluation(...)` as the read-only metrics fallback so tests and callers can still inject lightweight evaluation logic when needed.
4. Update exports and integration points.
   - Expose the new harness executor and evidence models from `taskflow.evolution`.
   - Keep runner integration compatible with both summary metrics and richer evaluation outcomes.
5. Cover the new executor path with focused tests and task docs.
   - Verify the summary fallback path still works.
   - Verify Sisyphus-backed evaluation evidence is captured on success and on launch failure.
   - Verify the guarded runner follow-up path still works on top of the updated harness contract.

## Risks

- If the task worktree is not aligned to the current local evolution baseline first, the harness executor work will land on the wrong architecture.
- If evaluation evidence is not returned through the harness result model, later report/MCP surfaces will need avoidable churn.
- If the Sisyphus-backed evaluator silently mutates live task state instead of isolated task/worktree state, it will violate the evolution isolation contract.

## Test Strategy

### Normal Cases

- [ ] Harness execution can produce completed evaluation metrics through the summary fallback path and through a Sisyphus-backed evaluation evidence path.

### Edge Cases

- [ ] Narrowed candidate scope and non-auto-executed Sisyphus evaluation requests still produce stable harness and runner results.

### Exception Cases

- [ ] Sisyphus evaluation or guarded follow-up launch failures surface actionable failure metadata, including isolated task evidence when available.

## Verification Mapping

- `Harness execution can produce completed evaluation metrics through the summary fallback path and through a Sisyphus-backed evaluation evidence path.` -> `uv run python -m unittest tests.test_evolution -v`
- `Narrowed candidate scope and non-auto-executed Sisyphus evaluation requests still produce stable harness and runner results.` -> `targeted regression test`
- `Sisyphus evaluation or guarded follow-up launch failures surface actionable failure metadata, including isolated task evidence when available.` -> `targeted regression test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
