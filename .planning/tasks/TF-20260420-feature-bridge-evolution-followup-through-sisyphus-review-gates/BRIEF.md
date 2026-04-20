# Brief

## Task

- Task ID: `TF-20260420-feature-bridge-evolution-followup-through-sisyphus-review-gates`
- Type: `feature`
- Slug: `bridge-evolution-followup-through-sisyphus-review-gates`
- Branch: `feat/bridge-evolution-followup-through-sisyphus-review-gates`

## Problem

- `src/sisyphus/evolution/handoff.py` defines the follow-up request contract and review-gate policy, but there is no implementation that turns that contract into a reviewable Sisyphus task.
- The repository already supports task requests, `source_context`, and follow-up metadata hooks, but evolution does not yet bridge its candidate/report outputs into that lifecycle.
- This slice must add the bridge without violating authority boundaries: evolution may request work, but it must not approve plans, freeze specs, run production provider execution, or promote itself.

## Desired Outcome

- An evolution follow-up request can be converted into a Sisyphus task request with evidence summaries and verification obligations attached.
- The created task remains reviewable and blocked behind the normal Sisyphus plan/spec/verify/receipt path.
- The bridge exposes enough metadata to connect future task execution back to the originating evolution run and candidate.

## Acceptance Criteria

- [ ] A bridge function accepts `EvolutionFollowupRequest` input and creates a Sisyphus follow-up task without auto-running provider execution.
- [ ] The created task records evolution lineage, evidence summaries, and verification obligations in metadata or source context that operators can inspect.
- [ ] Tests prove the bridge never performs plan approval, spec freeze, provider execution for production changes, or promotion.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add CLI or MCP surface changes in this slice.
- Do not widen the scope into promotion/invalidation persistence; this task ends at reviewable task request creation.
