# Changeset

## Summary

- Added shared gate helpers and moved audit, planning, closeout, and conformance paths onto them.
- Added lifecycle state/rule evaluation for plan/spec/execution/verify/close/promotion boundaries.
- Added action registry metadata with policy-safe, review-gated, and human-only risk levels.
- Added task observation rendering through CLI and MCP resources with stable observation hashes.
- Added first-pass reward and episode trace primitives for offline eval/RL loop work.
- Added regression tests for lifecycle rules, action boundaries, observation resources, reward scoring, episode trace writing, and conformance close gating.

## Verification

- `.venv/bin/python -m unittest discover -s tests -v` passed with 317 tests.
- `.venv/bin/python -m sisyphus.cli --repo /Users/jihokang/Documents/Sisyphus observe TF-20260614-feature-lifecycle-observation-foundation` passed.
- `git diff --check` passed.

## Follow-Ups

- Trace MCP tool calls and selected resource reads into `artifacts/episodes/*.jsonl`.
- Add curated evidence graph generation and closeout evidence completeness gates.
- Add an eval loop runner that aligns existing eval metrics with `RewardBreakdown`.
