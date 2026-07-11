# Plan

## Implementation Plan

1. Inspect README, AGENTS.md, and existing docs to avoid duplicating outdated terminology.
2. Update README introduction and workflow diagram to describe the harness loop:
   `state_t -> observation_t -> action_t -> transition -> state_t+1`.
3. Add observation-first rule to AGENTS.md while preserving MCP/lifecycle requirements.
4. Add research docs:
   - `docs/research/stateful-agent-harness.md`
   - `docs/research/harness-1-comparison.md`
5. Add focused harness docs:
   - `docs/rl-action-space.md`
   - `docs/reward-model.md`
   - `docs/episode-trace.md`
   - `docs/curated-evidence.md`
   - `docs/dataset-export.md`
6. Reference implemented modules and CLI surfaces from the completed runtime PRs.
7. Verify docs by checking paths, grep coverage for key CLI/module names, and Sisyphus verify.

## Risks

- Documentation could overclaim online RL/training; explicitly distinguish readiness/export from training.
- Docs could drift from implemented names; cite concrete modules and commands.
- AGENTS.md could appear to grant broader automation; keep judgment-gated actions conservative.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [x] README describes Sisyphus as a stateful harness/control plane.
- [x] AGENTS.md tells agents to read the observation resource before execution actions.
- [x] Docs reference observation/action/reward/trace/evidence/dataset export surfaces.

### Edge Cases

- [x] Docs state that RL training is future work, not current runtime behavior.
- [x] Action docs separate policy-allowed, review-gated, and human-only actions.

### Exception Cases

- [x] Missing referenced docs or stale command names are caught by grep/path checks.

## Verification Mapping

- `README and AGENTS guidance present` -> `rg` checks
- `Harness docs exist and reference implemented names` -> `test -f` and `rg` checks
- `Sisyphus task lifecycle verification` -> `sisyphus verify`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
