# Log

## Timeline

- Created task
- Reviewed verify, closeout, observation, MCP resource, and artifact projection code paths.
- Added `evidence_graph.py` for structured curated evidence schema, persistence, summaries, and closeout gates.
- Wired verify to write evidence graphs and closeout to enforce evidence gates for newly verified tasks.
- Exposed evidence through observation summaries and `task://<task-id>/evidence`.
- Added targeted and full regression coverage.
- Ran Sisyphus verify and confirmed the task evidence graph is complete.

## Notes

- Evidence close gates are opt-in via `meta.evidence_graph_required`, which is set by the new verify path. This avoids over-gating legacy verified tasks.
- `VERIFY.md` remains human-readable; the JSON evidence graph is the structured closeout input.

## Follow-ups

- Add richer spec-section and diff-linked evidence in a later pass.
