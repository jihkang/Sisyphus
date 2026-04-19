# Brief

## Task

- Task ID: `TF-20260419-feature-runtime-projection-feature-change-artifacts-root-replay`
- Type: `feature`
- Slug: `runtime-projection-feature-change-artifacts-root-replay`
- Branch: `feat/runtime-projection-feature-change-artifacts-root-replay`

## Problem

- `TF-20260416-feature-project-runtime-into-feature-change-artifacts` already verified the read-only runtime-projection slice, but that task is blocked only because its worktree predates the current root source-of-truth.
- The current root worktree now carries the authoritative migration baseline, so runtime projection must be replayed there instead of resumed inside the stale task worktree.
- This follow-up task must preserve the original narrow boundary: read-only feature-task runtime projection into reconstructable artifact views built on the artifact foundation and slot/claim models, plus focused tests only.

## Desired Outcome

- Sisyphus can project a feature task's current runtime state into reconstructable artifact views built on top of the artifact foundation and slot/claim models.
- The projection derives artifact records, slot bindings, verification claims, lineage, and task refs from existing task docs, lifecycle state, verify results, and branch metadata.
- The result stays scoped to adapter/projection logic and focused tests; it does not reroute live workflow authority into the artifact layer.

## Acceptance Criteria

- [ ] Introduce projection helpers that derive `FeatureChangeArtifact`-compatible views from an existing feature task record and task docs.
- [ ] The projection reuses the artifact foundation and slot/claim models instead of inventing parallel dict-based envelopes.
- [ ] The derived projection includes reconstructable lineage and task refs, current branch/base-branch context, verify-derived claim evidence, and stable slot bindings for spec, implementation candidate, tests, and verification claims.
- [ ] Focused tests cover a verified feature task projection, a pre-verify candidate projection, and invalid input such as an unsupported task type or missing required docs.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to adapter/projection logic plus focused tests.
- Do not replace live task workflow authority, add promotion evaluation, or expose MCP graph/UI behavior in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If projection logic mirrors `task.json` too literally, the artifact layer will inherit workflow-specific fields instead of emitting a reusable envelope.
- If verify results and branch metadata are not mapped into lineage and evidence cleanly, the resulting artifact view will not actually be reconstructable.
- If this task mutates task state while projecting, it will violate the intended hard-state authority boundary.
