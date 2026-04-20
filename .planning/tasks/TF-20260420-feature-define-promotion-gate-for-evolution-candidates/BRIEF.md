# Brief

## Task

- Task ID: `TF-20260420-feature-define-promotion-gate-for-evolution-candidates`
- Type: `feature`
- Slug: `define-promotion-gate-for-evolution-candidates`
- Branch: `feat/define-promotion-gate-for-evolution-candidates`

## Problem

- `EvolutionFitnessResult.eligible_for_promotion` is currently only a coarse boolean. It does not close over the actual hard-state obligations that matter for reviewable handoff or eventual promotion.
- The repository now has follow-up request artifacts, receipt projection, and verification-artifact projection, but there is no narrow evaluator that turns those artifacts plus guard/fitness state into an explicit promotion-gate result.
- Without that gate, later promotion or invalidation recording would either duplicate logic or rely on ad hoc booleans instead of reconstructable blocking conditions.

## Desired Outcome

- A small promotion-gate evaluator exists for evolution candidates and reports whether a candidate is blocked, ready for reviewable handoff, or fully eligible for promotion.
- The evaluator derives its answer from hard-state inputs: follow-up request artifact data, constraint/fitness acceptance, optional follow-up execution receipts, optional verification artifacts, and explicit blocking conditions.
- This slice stays evaluator-only. It must not record final promotion/invalidation envelopes or add new CLI/MCP surfaces.

## Acceptance Criteria

- [ ] The follow-up request artifact preserves the minimum promotion-gate inputs needed for later evaluation, including candidate lineage and recorded review gates.
- [ ] A promotion-gate helper evaluates hard-state obligations and returns an explicit result with blocking conditions instead of relying only on `fitness.eligible_for_promotion`.
- [ ] The evaluator can distinguish `blocked`, `ready_for_review`, and `eligible_for_promotion` without recording final promotion/invalidation decisions.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not record promotion/invalidation envelopes in this slice.
