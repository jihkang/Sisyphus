# Changeset

- Added a read-only `sisyphus evolution` CLI command group with `run`, `status`, `report`, and `compare`.
- Added `src/sisyphus/evolution/surface.py` to load and render evolution run artifacts from `.planning/evolution/runs/<run_id>`.
- Added CLI parser and surface tests in `tests/test_sisyphus.py` and `tests/test_evolution.py`.
- Updated evolution architecture/plan docs to describe the new read-only CLI surface and keep follow-up execution out of scope.
