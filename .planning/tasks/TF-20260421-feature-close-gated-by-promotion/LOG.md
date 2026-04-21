# Log

## Timeline

- Created task
- Inspected closeout and workflow transitions to find where verified tasks closed immediately after verify regardless of promotion state.
- Added promotion-aware close gating so promotable verified tasks park in `promotion_pending` instead of closing.
- Updated workflow auto-loop to stop on `promotion_pending` rather than repeatedly re-running verify/close cycles.
- Added focused and broader regression coverage for closeout, workflow parking, and non-regressed adjacent flows.

## Notes

- `run_close(...)` now consults the first-class promotion bundle and emits `PROMOTION_REQUIRED` when promotion has not reached a recorded terminal state.
- `promotion_pending` is expressed through `workflow_phase=promotion_pending` and `stage=promotion`, while successful close still transitions to `workflow_phase=closed`.

## Follow-ups

- `TF-20260421-feature-promotable-change-classification` can now decide when `promotion.required` flips on without needing to change closeout semantics again.
- `TF-20260421-feature-git-promotion-executor` can advance tasks out of `promotion_pending` by driving the promotion status machine toward `promotion_recorded`.
