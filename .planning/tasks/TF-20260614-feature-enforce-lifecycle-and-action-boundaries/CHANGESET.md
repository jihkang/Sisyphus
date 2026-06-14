# Changeset

## Summary

- Added `lifecycle_guard.py` to record shared lifecycle transition gates without adding eager import cycles.
- Extended verify transition rules so verification requires plan approval, spec freeze, and conformance readiness before audit side effects.
- Wired lifecycle transition checks into plan revision, spec freeze, subtask generation, verify, promotion execution, and merged PR receipt recording.
- Added regression tests for invalid direct mutation paths and MCP lifecycle gate reporting.
- Updated existing verification and promotion fixtures to make plan/spec/verify readiness explicit.

## Verification

- `/Users/jihokang/Documents/Sisyphus/.venv/bin/python -m unittest discover -s tests -v` passed with 324 tests in the task worktree.
- `git diff --check` passed.

## Follow-Ups

- Wire automatic episode trace capture for MCP/CLI actions.
- Add curated evidence graph and closeout evidence completeness gates.
