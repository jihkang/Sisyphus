# Plan

## Implementation Plan

1. Inspect the current follow-up request, receipt projection, verification projection, promotion-gate, and envelope-recording slices to identify the minimum invalidation change classes.
2. Define stable invalidation change and remediation-action vocabularies for evolution artifacts.
3. Implement a narrow evaluator that maps supported change classes to deduped remediation actions and stale-artifact refs.
4. Add focused tests for follow-up changes, execution-receipt changes, verification changes, combined changes, and unsupported change classes.
5. Update task docs and verification notes to match the rule-only behavior.

## Risks

- If change classes are too broad, downstream slices will still need ad hoc branching to recover precise next actions.
- If remediation actions are not deduped or ordered deterministically, later automation will become flaky.
- If unsupported changes silently fall back to a generic action set, stale envelopes may be rerecorded against the wrong source of truth.

## Test Strategy

### Normal Cases

- [ ] A follow-up request change marks the follow-up artifact stale and recommends follow-up recreation plus promotion-gate rerun.
- [ ] An execution-receipt change recommends receipt reprojection, verification reprojection, promotion-gate rerun, and envelope rerecording.

### Edge Cases

- [ ] Combined verification and envelope changes dedupe overlapping remediation actions while preserving stable action order.
- [ ] The invalidation outcome preserves run and candidate identity together with the stale artifact refs.

### Exception Cases

- [ ] Unsupported change classes fail with an actionable error instead of defaulting to a generic remediation path.
- [ ] Empty change sets fail clearly instead of fabricating a stale outcome with no cause.

## Verification Mapping

- `A follow-up request change marks the follow-up artifact stale and recommends follow-up recreation plus promotion-gate rerun.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `An execution-receipt change recommends receipt reprojection, verification reprojection, promotion-gate rerun, and envelope rerecording.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Combined verification and envelope changes dedupe overlapping remediation actions while preserving stable action order.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `The invalidation outcome preserves run and candidate identity together with the stale artifact refs.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Unsupported change classes fail with an actionable error instead of defaulting to a generic remediation path.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Empty change sets fail clearly instead of fabricating a stale outcome with no cause.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
