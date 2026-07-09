# Plan

## Implementation Plan

1. Consolidate repeated gate construction and deduplication into a shared utility.
2. Add a lifecycle state/rule module that evaluates transition validity without mutating task state.
3. Add an action registry that separates read-only, low-risk write, review-gated, and human-only actions.
4. Add an observation renderer that summarizes task state, gates, conformance, required docs, subtasks, verification, promotion, action candidates, and observation hash.
5. Expose observation through both CLI and MCP resource reads.
6. Add first-pass reward and episode trace primitives so eval metrics can map into future offline loop/RL datasets.
7. Add regression tests for the new primitives and the integration points they protect.

## Risks

- Lifecycle rules must not silently replace existing validated workflow operations; they should centralize gate reasoning first.
- Review-gated actions must remain blocked for policy execution even when the environment says a transition is otherwise possible.
- Reward and trace primitives should not imply online RL is ready; they only define the first stable offline interface.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `adds a small lifecycle/observation layer over existing task state without changing storage format`
- Confidence: `medium`
- Layer Impact: `layer-adding`
- Layer Decision Reason: `new modules define reusable lifecycle, observation, action, reward, trace, hash, and gate boundaries`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [x] Verified closed task with green conformance is allowed by lifecycle rules.
- [x] Observation for an open frozen task lists safe next actions and forbidden gated actions.
- [x] Reward scoring produces positive components for closed, verified, conformance-green outcomes.

### Edge Cases

- [x] Gate dedupe ignores volatile timestamps while preserving subtask-scoped gates.
- [x] Verified non-promotable tasks can close without promotion gates.
- [x] Observation remains stable enough to hash deterministically.

### Exception Cases

- [x] Spec freeze before plan approval is blocked.
- [x] Worker execution before plan approval/spec freeze is blocked.
- [x] Close before verification or with yellow/red conformance is blocked.
- [x] Human-gated close/promotion/approve/freeze actions are forbidden for policy execution.

## Verification Mapping

- `Verified closed task with green conformance is allowed by lifecycle rules` -> `.venv/bin/python -m unittest tests.test_lifecycle_rules -v`
- `Observation for an open frozen task lists safe next actions and forbidden gated actions` -> `.venv/bin/python -m unittest tests.test_mcp_core.McpCoreTests.test_reads_task_resources -v`
- `Reward scoring produces positive components for closed, verified, conformance-green outcomes` -> `.venv/bin/python -m unittest tests.test_reward -v`
- `Gate dedupe ignores volatile timestamps while preserving subtask-scoped gates` -> `.venv/bin/python -m unittest tests.test_lifecycle_rules.LifecycleRulesTests.test_gate_dedupe_ignores_created_at_but_preserves_subtask_scope -v`
- `Observation remains stable enough to hash deterministically` -> `.venv/bin/python -m sisyphus.cli --repo /Users/jihokang/Documents/Sisyphus observe TF-20260614-feature-lifecycle-observation-foundation`
- `Close before verification or with yellow/red conformance is blocked` -> `.venv/bin/python -m unittest tests.test_sisyphus.SisyphusVerifyTests.test_close_blocks_on_conformance_warning -v`
- `Full regression suite` -> `.venv/bin/python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
