# Log

## Timeline

- Created the task through the CLI fallback and froze it as a read-only CLI surface slice.
- Added `sisyphus evolution run/status/report/compare` as thin CLI wrappers over a new evolution surface helper that reads `.planning/evolution/runs/<run_id>` artifacts.
- Added loader/render tests and reran the targeted CLI/evolution suite plus `compileall`.

## Notes

- `src/sisyphus/evolution/surface.py` owns the run artifact loading and rendering so the CLI surface does not couple itself to MCP resource schemas or event-bus state.
- `run` stays read-only in this slice: it loads existing run artifacts rather than introducing promotion or follow-up execution behavior.
- Docs were updated to move the read-only CLI surface from future work into the implemented set.

## Follow-ups

- Add the corresponding MCP read surface in a later slice without duplicating the loader logic.
- Keep promotion, follow-up execution, and event envelope work separate from this read-only CLI path.
