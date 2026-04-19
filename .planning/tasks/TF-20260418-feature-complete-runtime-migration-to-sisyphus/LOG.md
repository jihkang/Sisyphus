# Log

## Timeline

- 2026-04-18: Created the umbrella migration task and split the work into three implementation slices.
- 2026-04-18: Closed `TF-20260418-feature-migrate-core-runtime-modules-to-sisyphus` after moving the non-evolution core runtime into `src/sisyphus`.
- 2026-04-18: Closed `TF-20260418-feature-migrate-evolution-and-mcp-modules-to-sisyphus` after moving MCP and evolution implementations into `src/sisyphus`.
- 2026-04-18: Closed `TF-20260418-feature-invert-taskflow-into-compatibility-shims` after moving CLI ownership into `src/sisyphus` and tightening the compatibility alias boundary.
- 2026-04-18: Re-ran focused regression coverage for the final package boundary and confirmed the staged migration result.

## Notes

- The migration is complete in terms of runtime authority: `sisyphus` is now the implementation root for the primary runtime surfaces.
- `taskflow` remains intentionally supported as a compatibility package; removing it entirely is a later product decision, not part of this task.
- All three slice tasks were verified and closed before closing this umbrella task.

## Follow-ups

- Decide whether to keep the compatibility package long-term or schedule a later deprecation/removal task.
- Optionally rewrite the remaining historical `src/taskflow/*.py` source files into literal tiny wrappers if we want the source tree to mirror the runtime boundary more explicitly.
