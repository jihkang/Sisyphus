# Plan

## Implementation Plan

1. Inspect the current focused evolution tests and identify the minimum reusable fixture pieces needed for a vertical artifact-cycle flow.
2. Add a happy-path repo-local integration test that exercises run orchestration, isolated candidate materialization, follow-up bridge, receipt projection, verification projection, promotion-gate evaluation, and decision-envelope recording.
3. Add a blocked or stale-path integration test that reuses the same lineage but proves invalidation actions and invalidation-style envelope handling still compose.
4. Assert evolution event envelopes and lineage fields so the vertical test covers both hard-state artifacts and event-bus observability.
5. Update task docs and verification notes to reflect the final end-to-end test scope.

## Risks

- If the vertical test uses too much mocking, it will stop proving real cross-module composition and collapse back into another unit test.
- If the fixture setup mutates the main test repo instead of isolated temp repos/worktrees, the test may become flaky or hide isolation regressions.
- If lineage assertions are too shallow, the test may still pass while run/candidate/task IDs drift across the artifact cycle.

## Test Strategy

### Normal Cases

- [ ] A happy-path artifact cycle keeps run ID, candidate ID, follow-up task ID, and event lineage aligned from `execute_evolution_run` through decision-envelope recording.

### Edge Cases

- [ ] The vertical flow includes isolated candidate materialization so evaluation artifacts are exercised in a worktree-like path rather than only through synthetic refs.
- [ ] Event envelopes emitted during the vertical flow remain correlated with the same artifact lineage as the hard-state objects.

### Exception Cases

- [ ] A blocked or stale-path artifact cycle records invalidation-style outcomes and deterministic remediation actions against the same follow-up lineage.

## Verification Mapping

- `A happy-path artifact cycle keeps run ID, candidate ID, follow-up task ID, and event lineage aligned from execute_evolution_run through decision-envelope recording.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `The vertical flow includes isolated candidate materialization and correlated event envelopes.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A blocked or stale-path artifact cycle records invalidation-style outcomes and deterministic remediation actions against the same follow-up lineage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
