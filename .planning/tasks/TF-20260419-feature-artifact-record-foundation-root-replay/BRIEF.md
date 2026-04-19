# Brief

## Task

- Task ID: `TF-20260419-feature-artifact-record-foundation-root-replay`
- Type: `feature`
- Slug: `artifact-record-foundation-root-replay`
- Branch: `feat/artifact-record-foundation-root-replay`

## Problem

- `TF-20260416-feature-implement-artifact-record-foundation` already defined and verified the base artifact-record slice, but that task is blocked only because its stale task worktree predates the current root source-of-truth.
- The current root worktree now carries the active `taskflow` -> `sisyphus` migration baseline, so the artifact foundation must be replayed on top of that adopted baseline rather than resumed in the old worktree.
- This follow-up task must preserve the original narrow boundary: durable artifact record models, reconstruction-envelope primitives, stable serialization, and focused tests only.

## Desired Outcome

- Sisyphus has typed repository-local models for durable artifact records and their reconstruction-envelope primitives on top of the current root-adopted baseline.
- The model can serialize and deserialize cleanly without depending on live task mutation or MCP surface work.
- The result stays narrow enough that later slot-binding, runtime projection, promotion, and MCP graph tasks can layer on top without renaming the core record shape.

## Acceptance Criteria

- [ ] Introduce typed models or schema drafts for `ArtifactRecord`, `CompositeArtifactRecord`, `TaskSpecRef`, `TaskRunRef`, and reconstruction-envelope primitives such as artifact refs, lineage, and invariant records.
- [ ] The model layer preserves the architectural boundary: artifacts are durable state, while task specs and task runs are references inside the envelope rather than replacements for live authority.
- [ ] Records can round-trip through a stable serialization shape suitable for repository-local JSON persistence.
- [ ] Focused tests cover a minimal valid artifact record, a composite artifact record with lineage and invariants, and invalid input or malformed reconstruction data.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to data model definition, serialization shape, and focused tests.
- Do not implement slot binding, runtime projection, promotion evaluation, invalidation policy execution, workflow replacement, or MCP graph exposure in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the base artifact record shape is too thin, later tasks will reintroduce parallel envelopes for lineage, invariants, and task references.
- If this task pulls slot binding or promotion policy into the foundation, the next tasks lose a clean layering boundary.
- If serialization is not explicit and stable, repository-local persistence will drift between call sites.
