# Changeset

## Summary

- Added structured evidence graph support under `artifacts/evidence/evidence-graph.json`.
- Extended verify to persist curated evidence and closeout to gate missing or unsupported high-importance evidence.
- Exposed evidence state in task observation and via `task://<task-id>/evidence`.

## Files

- `src/sisyphus/evidence_graph.py`
- `src/sisyphus/audit.py`
- `src/sisyphus/closeout.py`
- `src/sisyphus/observation.py`
- `src/sisyphus/mcp_core.py`
- `tests/test_evidence_graph.py`
- `tests/test_mcp_core.py`
- `tests/test_sisyphus.py`

## Compatibility

- Existing verified tasks are not evidence-gated unless the new verify path marks `meta.evidence_graph_required`.
