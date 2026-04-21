# Brief

## Task

- Task ID: `TF-20260421-feature-close-gated-by-promotion`
- Type: `feature`
- Slug: `close-gated-by-promotion`
- Branch: `feat/close-gated-by-promotion`

## Problem

- Gate closeout on promotion state
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Change closeout so promotion.required=true tasks do not go directly from verify passed to closed. Introduce an explicit promotion-pending stage or equivalent state transition and keep close eligibility tied to promotion completion.

## Desired Outcome

- Verified tasks that still require promotion do not close immediately.
- Closeout moves promotable verified tasks into an explicit `promotion_pending` state instead of treating them as generic blocked failures.
- Workflow auto-loop stops on `promotion_pending` instead of repeatedly re-verifying and re-closing the same task.

## Acceptance Criteria

- [x] `run_close(...)` blocks verified tasks whose first-class promotion state is still pending.
- [x] Promotion-blocked tasks are left in an explicit `promotion_pending` workflow phase with a `promotion` stage instead of a generic blocked/audit state.
- [x] Close still succeeds normally once promotion is `promotion_recorded`.
- [x] Workflow auto-loop does not churn on tasks already parked in `promotion_pending`.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
