# Log

## Timeline

- Created task
- Identified that promotion state lived only in ad hoc `meta["promotion"]` payloads and was not part of the canonical task schema.
- Added a shared promotion-state normalization helper and routed task defaults plus load/list/save through the first-class promotion bundle.
- Updated merge receipt recording, MCP task projections, service summaries, and evolution receipt projection to read the first-class promotion state.
- Added focused and broader regression coverage for task defaults, legacy migration, MCP projections, merge receipts, and evolution receipts.

## Notes

- `record_merged_pull_request(...)` previously wrote only `meta["promotion"]`, which left later promotion-aware workflow tasks without a stable schema to build on.
- Default receipt paths now exist in the promotion bundle, but downstream receipt readers only treat promotion as materialized when the promotion status says it was actually recorded.

## Follow-ups

- `TF-20260421-feature-close-gated-by-promotion` can now gate close on `task["promotion"]` instead of parsing ad hoc merge metadata.
- `TF-20260421-feature-promotable-change-classification` and `TF-20260421-feature-git-promotion-executor` can write to the same bundle instead of inventing new side-channel state.
