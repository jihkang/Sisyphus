# Brief

## Task

- Task ID: `TF-20260420-feature-define-invalidation-rules-for-evolution-artifacts`
- Type: `feature`
- Slug: `define-invalidation-rules-for-evolution-artifacts`
- Branch: `feat/define-invalidation-rules-for-evolution-artifacts`

## Problem

- Promotion and invalidation envelopes now exist, but there is still no explicit invalidation rule layer that says which upstream changes make those records stale and what recomputation action should happen next.
- Without a rule matrix, downstream automation would need to guess when to recreate a follow-up request, reproject receipts, reproject verification, rerun the promotion gate, or rerecord envelopes.
- This slice should define change classes and evaluator helpers only; it must not add event publication or full orchestration.

## Desired Outcome

- Evolution artifact invalidation is driven by explicit change classes rather than ad hoc branching logic.
- A narrow evaluator maps follow-up request changes, execution receipt changes, verification changes, review-gate changes, and envelope changes to stable remediation actions.
- The slice stays rule-only. It does not add event-bus publication, CLI/MCP surfaces, or end-to-end orchestration.

## Acceptance Criteria

- [ ] An invalidation-rule helper classifies supported evolution change classes and returns stable remediation actions.
- [ ] The returned actions cover at least follow-up recreation, receipt reprojection, verification reprojection, promotion-gate rerun, and envelope rerecording.
- [ ] Unsupported change classes fail loudly instead of silently defaulting to an unsafe action set.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add event-bus publication, CLI/MCP surfaces, or orchestration loops in this slice.
