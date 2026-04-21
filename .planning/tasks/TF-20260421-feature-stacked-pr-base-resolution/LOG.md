# Log

## Timeline

- Created task
- Added base resolution metadata to the promotion bundle and executor
- Added stacked lineage regression coverage for open parent, merged parent, and explicit override cases
- Ran targeted and full unittest regression suites

## Notes

- `base_override`, `base_source`, `base_reason`, and `resolved_parent_branch` now explain why a promotion used its chosen PR base.
- Stacked promotions prefer an open parent task branch, but switch back to the parent merge target once the parent is already recorded as merged.
- Execution receipts now preserve stacked lineage details for later audit.

## Follow-ups

- Use the same lineage metadata when parent merge retarget and reverify logic lands.
