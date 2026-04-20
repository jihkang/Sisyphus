# Plan

## Implementation Plan

1. Inspect the current hard-state inputs that already exist for evolution follow-up flow: `EvolutionFollowupRequestArtifact`, `EvolutionFitnessResult`, receipt projection, and verification projection.
2. Extend the follow-up request artifact only as much as needed to preserve promotion-gate inputs in hard state, especially candidate lineage and recorded review gates.
3. Implement a narrow promotion-gate evaluator that combines follow-up request data, constraint/fitness acceptance, optional receipt projection, and optional verification artifacts into an explicit gate result with blocking conditions.
4. Add focused tests for `blocked`, `ready_for_review`, and `eligible_for_promotion` states, plus failure or mismatch cases where execution or verification evidence does not line up with the follow-up request artifact.
5. Update task docs and verification notes to match the implemented evaluator-only behavior.

## Risks

- The current follow-up request artifact is thinner than the data now needed for promotion-gate evaluation, so this slice may need a narrow schema extension.
- If the evaluator treats missing execution or verification evidence as implicit success, the evolution graph will drift away from actual hard-state obligations.
- If lineage or follow-up task identity mismatches are ignored, later promotion recording will have no reliable basis for reconstructable decisions.

## Test Strategy

### Normal Cases

- [ ] A candidate with accepted constraints/fitness and a reviewable follow-up request reports `ready_for_review` even before follow-up execution evidence exists.
- [ ] A candidate with accepted constraints/fitness, aligned follow-up receipts, and passing verification artifacts reports `eligible_for_promotion`.

### Edge Cases

- [ ] Narrowed review-gate sequences remain preserved on the follow-up request artifact and still allow `ready_for_review` when other handoff prerequisites are satisfied.
- [ ] Execution and verification evidence refs are surfaced in the gate result so later promotion-envelope recording can reuse them without recomputing lineage.

### Exception Cases

- [ ] Missing review gates, rejected/pending fitness, or rejected constraints keep the gate in `blocked` with explicit blocker codes instead of a generic false boolean.
- [ ] Mismatched follow-up execution or verification lineage fails loudly instead of silently treating unrelated evidence as valid promotion input.

## Verification Mapping

- `A candidate with accepted constraints/fitness and a reviewable follow-up request reports ready_for_review even before follow-up execution evidence exists.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A candidate with accepted constraints/fitness, aligned follow-up receipts, and passing verification artifacts reports eligible_for_promotion.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Narrowed review-gate sequences remain preserved on the follow-up request artifact and still allow ready_for_review when other handoff prerequisites are satisfied.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Execution and verification evidence refs are surfaced in the gate result so later promotion-envelope recording can reuse them without recomputing lineage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Missing review gates, rejected/pending fitness, or rejected constraints keep the gate in blocked with explicit blocker codes instead of a generic false boolean.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Mismatched follow-up execution or verification lineage fails loudly instead of silently treating unrelated evidence as valid promotion input.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
