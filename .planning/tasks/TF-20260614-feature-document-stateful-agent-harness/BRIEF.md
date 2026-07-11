# Brief

## Task

- Task ID: `TF-20260614-feature-document-stateful-agent-harness`
- Type: `feature`
- Slug: `document-stateful-agent-harness`
- Branch: `feat/document-stateful-agent-harness`

## Problem

- Document Sisyphus as a stateful agent harness
- Original request: Update project documentation to describe Sisyphus as a stateful harness/control plane for AI-assisted software work.

Scope:
- Update README introduction with state_t -> observation_t -> action_t -> transition -> state_t+1 positioning.
- Add observation-first guidance to AGENTS.md: read task://<task-id>/observation before choosing execution actions and do not infer lifecycle state from chat history.
- Add docs for action space/risk levels, reward model, episode traces, curated evidence, and Harness-1 comparison.
- Make clear that RL training is future work; current design first closes environment interfaces, evidence, trace, and eval metrics.

Acceptance criteria:
- README first section describes Sisyphus as a stateful agent harness, not only a task lifecycle utility.
- AGENTS.md includes observation-first rule and preserves judgment boundary for approve/freeze/close/promotion.
- docs explain which actions are policy-allowed, review-gated, or human-only.
- docs distinguish eval/reward loop readiness from online RL training.

Dependency: can run in parallel with runtime tasks, but should reference actual code names from the foundation PR.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [x] README introduction positions Sisyphus as a stateful agent harness/control plane.
- [x] AGENTS.md adds observation-first guidance using `task://<task-id>/observation`.
- [x] Research docs explain stateful harness structure and Harness-1 comparison without claiming live RL training is implemented.
- [x] Action space, reward model, episode trace, curated evidence, and dataset export docs reference the implemented module/CLI names.
- [x] Docs preserve the judgment boundary for approve, freeze, close, and promotion actions.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep this task documentation-only; no runtime behavior changes.
