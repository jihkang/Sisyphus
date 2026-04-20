# Brief

## Task

- Task ID: `TF-20260420-feature-record-evolution-promotion-invalidation-envelope`
- Type: `feature`
- Slug: `record-evolution-promotion-invalidation-envelope`
- Branch: `feat/record-evolution-promotion-invalidation-envelope`

## Problem

- The repository now has follow-up request artifacts, receipt projection, verification projection, and a promotion-gate evaluator, but there is still no hard-state envelope that records the resulting promotion or invalidation decision.
- Without a stable envelope, later audit, replay, or stale-state analysis would need to recompute decisions from scattered artifacts instead of reading one reconstructable decision record.
- This next slice should record current decision state only; it should not broaden into event-bus publication or invalidation-policy derivation.

## Desired Outcome

- The system can convert a promotion-gate result plus its supporting artifacts into a stable hard-state envelope for promotion or invalidation.
- The recorded envelope preserves decision status, claim, blocker detail, evidence refs, and follow-up task linkage.
- The slice remains persistence-only and does not add event-bus or surface integrations.

## Acceptance Criteria

- [ ] Promotion or invalidation recording produces reconstructable hard-state records from existing evolution artifacts and gate outputs.
- [ ] The recorded envelope preserves decision metadata, blocker detail, evidence refs, and follow-up task linkage.
- [ ] The slice does not add event-bus integration, invalidation-policy derivation, or new CLI/MCP surfaces.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add event-bus publication or invalidation-matrix logic in this slice.
