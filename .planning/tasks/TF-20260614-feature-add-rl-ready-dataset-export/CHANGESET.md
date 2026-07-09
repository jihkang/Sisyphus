# Changeset

## Summary

- Added deterministic offline dataset export for Sisyphus episode traces.
- Added `sisyphus dataset export --format sft|rl [--task-id <id>] [--output <path>]`.
- Added SFT records with observation-hash/state-before payloads and action JSON messages.
- Added RL records with observation/action/result/transition, terminal reward, metrics, and test-first metadata.
- Added focused regression tests and CLI parser coverage.

## Files Changed

- `src/sisyphus/dataset_export.py`
- `src/sisyphus/cli.py`
- `tests/test_dataset_export.py`
- `tests/test_sisyphus.py`

## Verification

- Targeted dataset export tests passed.
- CLI `dataset export` smoke test passed.
- Full repository unittest suite passed.
- Sisyphus verify passed with no gates.
