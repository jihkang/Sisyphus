# Changeset

## Summary

- Added a read-only `sisyphus.eval` loop projection for recorded task state, episode actions, evidence, reward, and terminal outcome.
- Extended reward scoring with stable metric names, evidence completeness, action efficiency, false-close facts, conformance drift penalties, missing-evidence penalties, and excessive-action penalties.
- Added `sisyphus eval loop <task-id> [--json]` CLI output.
- Exposed the missing test-first implementation loop as an explicit `test_first.status = todo` phase list for follow-up work.

## Files

- `src/sisyphus/reward.py`
- `src/sisyphus/eval/__init__.py`
- `src/sisyphus/eval/loop.py`
- `src/sisyphus/cli.py`
- `tests/test_reward.py`
- `tests/test_eval_loop.py`
- `tests/test_sisyphus.py`

## Verification

- Targeted reward/eval/parser tests passed.
- Full unittest suite passed: 340 tests.
- `git diff --check` passed.
- Eval loop JSON smoke test passed and includes the test-first TODO phase.
