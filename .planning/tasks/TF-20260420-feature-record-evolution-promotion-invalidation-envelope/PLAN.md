# Plan

## Implementation Plan

1. Inspect the current promotion-gate evaluator, follow-up request artifact, receipt projection, verification projection, and existing `PromotionDecisionArtifact` / `EvolutionInvalidationRecord` contracts.
2. Define the minimum envelope shape needed to record current promotion or invalidation state without recomputing evidence later.
3. Implement a narrow recorder that converts gate results plus existing evidence refs into stable hard-state promotion and invalidation records.
4. Add focused tests for promotion-eligible recording, blocked/invalidation-style recording, and envelope linkage back to the follow-up task and evidence artifacts.
5. Update task docs and verification notes to match the implemented recording-only behavior.

## Risks

- If the recorder drops blocker detail or evidence refs, later audit and replay will still need to recompute decisions from scattered state.
- If promotion and invalidation records do not preserve follow-up task linkage, downstream rollback or stale-state analysis will lose reconstructability.
- If this slice broadens into event publication or invalidation policy derivation, it will overlap the remaining dedicated tasks.

## Test Strategy

### Normal Cases

- [ ] A promotion-eligible gate result records a stable promotion decision artifact with decision metadata, claim, evidence refs, and follow-up task linkage.
- [ ] A blocked gate result records a stable invalidation-style record that preserves blocker detail and the affected artifacts.

### Edge Cases

- [ ] Evidence refs from follow-up request, execution receipts, and verification artifacts remain deduped and stable in the recorded envelope.
- [ ] Recorded envelopes keep the original evolution run and candidate identity even when multiple blocker conditions are present.

### Exception Cases

- [ ] Missing gate outputs or missing follow-up lineage fails loudly instead of writing a partial or misleading decision envelope.
- [ ] Unsupported decision status fails with an actionable error instead of silently coercing to promotion or invalidation.

## Verification Mapping

- `A promotion-eligible gate result records a stable promotion decision artifact with decision metadata, claim, evidence refs, and follow-up task linkage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A blocked gate result records a stable invalidation-style record that preserves blocker detail and the affected artifacts.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Evidence refs from follow-up request, execution receipts, and verification artifacts remain deduped and stable in the recorded envelope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Recorded envelopes keep the original evolution run and candidate identity even when multiple blocker conditions are present.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Missing gate outputs or missing follow-up lineage fails loudly instead of writing a partial or misleading decision envelope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Unsupported decision status fails with an actionable error instead of silently coercing to promotion or invalidation.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
