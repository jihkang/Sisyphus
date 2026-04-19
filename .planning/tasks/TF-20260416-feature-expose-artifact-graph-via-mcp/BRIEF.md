# Brief

## Task

- Task ID: `TF-20260416-feature-expose-artifact-graph-via-mcp`
- Type: `feature`
- Slug: `expose-artifact-graph-via-mcp`
- Branch: `feat/expose-artifact-graph-via-mcp`

## Problem

- expose artifact graph via mcp
- Original request: Expose the new artifact graph and FeatureChangeArtifact projections through a read-first MCP surface. Add resources or tools that let operators inspect artifact records, slot bindings, verification claims, and promotion or invalidation summaries once the core models exist. Keep scope read-only first and avoid mutation tooling in this slice.

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
