# Brief

## Task

- Task ID: `TF-20260415-feature-implement-actual-evolution-harness-executor`
- Type: `feature`
- Slug: `implement-actual-evolution-harness-executor`
- Branch: `feat/implement-actual-evolution-harness-executor`

## Problem

- implement-actual-evolution-harness-executor
- Original request: Implement the next evolution slice: replace the current summary-only harness default with an actual Sisyphus-backed execution evaluator shape. The goal is to make the evolution harness capable of executing a bounded evaluation flow against isolated task/worktree context and returning real metrics/evidence hooks, while preserving live-state isolation and explicit policy injection. Start from the existing evolution runner and follow-up execution work and keep scope focused on harness execution rather than MCP surface or promotion flow.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] The requested workflow is implemented or corrected.
- [ ] The task docs reflect the actual implementation and verification scope.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
