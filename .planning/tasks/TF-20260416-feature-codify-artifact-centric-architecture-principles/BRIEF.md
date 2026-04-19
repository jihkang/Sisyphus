# Brief

## Task

- Task ID: `TF-20260416-feature-codify-artifact-centric-architecture-principles`
- Type: `feature`
- Slug: `codify-artifact-centric-architecture-principles`
- Branch: `feat/codify-artifact-centric-architecture-principles`

## Problem

- codify artifact-centric architecture principles
- Original request: Codify the artifact-centric Sisyphus architecture principles from the current design summary into repository docs, preserving the hard-state/soft-cognition split, reconstructability requirement, and promotion/invalidation model. Then identify the best concrete next design step to implement or specify next.

## Desired Outcome

- The architecture docs clearly define Sisyphus as an artifact-centric work system with a durable-state authority boundary.
- The documentation records the best next design step concretely enough to guide the next implementation or specification pass.

## Acceptance Criteria

- [x] `docs/architecture.md` records the hard-state versus soft-cognition split, reconstructability, verification, promotion, and invalidation model.
- [x] `docs/self-evolution-mcp-plan.md` clarifies that Hermes-like capabilities may be absorbed as intelligence but do not own runtime authority.
- [x] The next design lock identifies a concrete first composite artifact protocol to define next.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
