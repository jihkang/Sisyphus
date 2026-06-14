# Brief

## Task

- Task ID: `TF-20260614-feature-lifecycle-observation-foundation`
- Type: `feature`
- Slug: `lifecycle-observation-foundation`
- Branch: `feat/lifecycle-observation-foundation`

## Problem

- Sisyphus needs to own lifecycle bookkeeping instead of requiring agents to infer task state from scattered resources or chat history.
- Existing gate creation/deduplication logic is duplicated across audit, planning, closeout, and conformance paths.
- The current codebase has eval metrics and evolution harness pieces, but no explicit reward bridge, observation schema, action registry, or episode trace primitive for a future loopback/RL workflow.

## Desired Outcome

- Lifecycle transition rules are centralized and testable.
- Agents can read a compact task observation through CLI and MCP resources.
- Policy-safe actions are separated from review-gated and human-only actions.
- Verification/eval work has first-class reward and episode trace primitives without adding an online RL trainer.
- Existing duplicated gate helpers are consolidated into a shared utility.

## Acceptance Criteria

- [x] Lifecycle transition evaluation blocks invalid close/spec/execution paths.
- [x] Observation rendering exposes task status, conformance, gates, required docs, subtasks, verification, action candidates, and a stable hash.
- [x] CLI exposes `sisyphus observe <task-id>` and `sisyphus observe <task-id> --json`.
- [x] MCP resource listing includes `task://<task-id>/observation`.
- [x] Action registry records policy-safe, review-gated, and human-only action boundaries.
- [x] Reward and episode trace primitives exist for offline loop/eval work.
- [x] Regression tests cover lifecycle, observation, reward, trace, conformance close gating, and MCP resource access.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
