# Changeset

## Summary

- Added a deterministic test-first loop evaluator for recorded episode traces.
- Wired eval loop JSON to report concrete `test_first` status, observed phases, missing phases, and violations.
- Added `sisyphus eval test-first <task-id> [--episode-id] [--json]` as a read-only CLI check.
- Added regression coverage for satisfied, incomplete, violated, and not-recorded test-first episodes.

## Files Changed

- `src/sisyphus/test_first.py`
- `src/sisyphus/eval/loop.py`
- `src/sisyphus/cli.py`
- `tests/test_test_first.py`
- `tests/test_eval_loop.py`
- `tests/test_sisyphus.py`

## Verification

- Targeted unit tests passed.
- CLI JSON smoke test passed.
- Full repository unittest suite passed.
- Sisyphus verify passed with no gates.
