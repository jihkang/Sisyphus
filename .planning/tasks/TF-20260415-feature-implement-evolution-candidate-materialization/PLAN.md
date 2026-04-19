# Plan

## Implementation Plan

1. Align this task worktree with the latest local evolution baseline so the slice starts from the stage-aware runner and Sisyphus-backed harness executor instead of the older `main` snapshot.
2. Add a bounded `evolution.mutators` layer for Phase 1 text/policy targets that can materialize baseline snapshots and candidate-only source rewrites inside isolated evaluation task worktrees without touching live task state.
3. Extend the harness Sisyphus evaluation path so evaluation evidence records the materialization manifest, touched files, and target ids, and so provider execution receives the materialized owned paths.
4. Add focused regression tests for baseline snapshots, candidate materialization, evidence plumbing, and failure handling, then update task docs to reflect the implemented scope.

## Risks

- This slice depends on a prior local evolution worktree that is not yet merged to `main`, so the task worktree must be explicitly aligned before implementation.
- Targeted text rewrites are intentionally bounded to the current Phase 1 symbols; if source anchors drift, materialization should fail loudly instead of silently producing partial mutations.
- Evaluation tasks must remain isolated; candidate rewrites must only land in the dedicated Sisyphus evaluation worktree and its task-local artifacts.

## Test Strategy

### Normal Cases

- [ ] A baseline evaluation task captures task-local source snapshots and emits materialization evidence without mutating the evaluation worktree sources.
- [ ] A candidate evaluation task applies bounded Phase 1 text/policy rewrites in its isolated worktree and exposes the manifest and touched files through evaluation evidence.

### Edge Cases

- [ ] Multiple selected targets preserve registry order while materializing only the requested source files.
- [ ] Materialization artifacts stay task-local and do not leak writes back into the source repository root.

### Exception Cases

- [ ] Missing rewrite anchors or an unavailable evaluation worktree fail the evaluation with actionable evidence instead of silently continuing.

## Verification Mapping

- `A baseline evaluation task captures task-local source snapshots and emits materialization evidence without mutating the evaluation worktree sources.` -> `python -m unittest tests.test_evolution -v`
- `A candidate evaluation task applies bounded Phase 1 text/policy rewrites in its isolated worktree and exposes the manifest and touched files through evaluation evidence.` -> `python -m unittest tests.test_evolution -v`
- `Multiple selected targets preserve registry order while materializing only the requested source files.` -> `python -m unittest tests.test_evolution -v`
- `Materialization artifacts stay task-local and do not leak writes back into the source repository root.` -> `python -m unittest tests.test_evolution -v`
- `Missing rewrite anchors or an unavailable evaluation worktree fail the evaluation with actionable evidence instead of silently continuing.` -> `python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
