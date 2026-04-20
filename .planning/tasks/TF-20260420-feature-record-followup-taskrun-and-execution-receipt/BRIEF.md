# Brief

## Task

- Task ID: `TF-20260420-feature-record-followup-taskrun-and-execution-receipt`
- Type: `feature`
- Slug: `record-followup-taskrun-and-execution-receipt`
- Branch: `feat/record-followup-taskrun-and-execution-receipt`

## Problem

- `bridge_evolution_followup_request(...)` can now create reviewable Sisyphus follow-up tasks with evolution lineage in source context, but there is still no mapper that turns an executed follow-up task back into evolution receipt artifacts.
- The repository already has task-local verify results, verify documents, optional promotion receipts, and core `TaskRunRef` projection logic. This slice needs an evolution-specific receipt mapper on top of those primitives.
- The mapper must fail loudly when an evolution follow-up task has no actual receipt evidence, instead of inventing execution linkage.

## Desired Outcome

- An executed evolution follow-up task can be projected into `ExecutionReceiptArtifact` and `TaskRunRef` data anchored to the originating evolution run.
- Receipt locators point at real follow-up task artifacts such as `VERIFY.md` or the promotion receipt file when present.
- The mapping stays receipt-only; it does not introduce promotion decisions or verification-claim linkage.

## Acceptance Criteria

- [ ] A receipt-linkage helper can load an executed evolution follow-up task and emit stable `ExecutionReceiptArtifact` plus `TaskRunRef` data.
- [ ] Verify-command receipts and optional promotion receipt locators are derived from real task artifacts instead of fabricated placeholders.
- [ ] Missing verify results or missing referenced receipt files fail with actionable errors.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add promotion/invalidation decisions or verification-claim linkage in this slice.
