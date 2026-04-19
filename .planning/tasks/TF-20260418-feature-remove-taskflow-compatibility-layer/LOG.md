# Log

## Timeline

- 2026-04-18: Inventoried remaining `taskflow` references across live code, tests, docs, and packaging metadata.
- 2026-04-18: Removed reverse aliasing from `sisyphus`, deleted the live `src/taskflow/` package, and removed the `taskflow` console entrypoint from `pyproject.toml`.
- 2026-04-18: Updated repo-local tests and live docs to target `sisyphus` directly.
- 2026-04-18: Kept `.taskflow.toml` fallback and `taskflow.event.v1` intact as intentionally preserved persisted compatibility.
- 2026-04-18: Ran a canonical-import smoke check and the focused runtime regression suite after package removal.

## Notes

- The package alias layer is gone; `taskflow` is no longer importable from the live source tree.
- The distribution name in `pyproject.toml` is still `taskflow-kit`; that is packaging metadata and may be renamed in a separate task if desired.

## Follow-ups

- Decide whether the distribution/package metadata should also be renamed away from `taskflow-kit`.
- Decide whether `.taskflow.toml` fallback and `taskflow.event.v1` should be deprecated in a later compatibility-removal task.
