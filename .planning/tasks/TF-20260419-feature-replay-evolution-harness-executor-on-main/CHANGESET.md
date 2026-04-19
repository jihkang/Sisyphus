# Changeset

## Scope

- Replay the missing evaluation-only evolution harness executor onto the current `main` baseline.

## Changes

- Added summary-based harness execution and bounded isolated Sisyphus evaluation helpers in `src/sisyphus/evolution/harness.py`
- Exported new harness execution types, constants, and helper functions from `src/sisyphus/evolution/__init__.py`
- Expanded `tests/test_evolution.py` to cover summary execution, bounded Sisyphus-backed evidence capture, and failed evaluation handling
- Updated `docs/self-evolution-mcp-plan.md` and `docs/architecture.md` to describe the implemented execution slice accurately

## Out Of Scope

- Candidate materialization
- Full worktree-backed harness execution
- Production follow-up bridge
- Promotion and invalidation recording
- MCP/CLI evolution ingress
