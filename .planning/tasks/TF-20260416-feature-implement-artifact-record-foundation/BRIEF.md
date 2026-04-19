# Brief

## Task

- Task ID: `TF-20260416-feature-implement-artifact-record-foundation`
- Type: `feature`
- Slug: `implement-artifact-record-foundation`
- Branch: `feat/implement-artifact-record-foundation`

## Problem

- The repository has architecture and protocol docs for artifact-centric runtime state, but it still lacks a concrete model layer for durable artifact records.
- Without a typed artifact foundation, the later slot-binding, runtime projection, promotion, and MCP graph tasks will either invent parallel shapes or serialize ad hoc dicts that cannot be reconstructed consistently.
- This task needs to lock the first repository-local artifact record model, not the full policy engine.

## Desired Outcome

- Sisyphus has typed repository-local models for durable artifact records and their reconstruction envelope primitives.
- The initial model can serialize and deserialize cleanly without depending on live task mutation or MCP surface work.
- The result is narrow enough that later tasks can layer slot bindings, verification claims, runtime projection, and promotion policy on top without renaming the core record shape.

## Acceptance Criteria

- [ ] Introduce typed models or schema drafts for `ArtifactRecord`, `CompositeArtifactRecord`, `TaskSpecRef`, `TaskRunRef`, and reconstruction-envelope primitives such as artifact refs, lineage, and invariant records.
- [ ] The model layer preserves the current architectural boundary: artifacts are durable state, while task specs and task runs are references inside the envelope rather than replacements for live authority.
- [ ] Records can round-trip through a stable serialization shape suitable for repository-local JSON persistence.
- [ ] Focused tests cover a minimal valid artifact record, a composite artifact record with lineage and invariants, and invalid input or malformed reconstruction data.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to data model definition, serialization shape, and focused tests.
- Do not implement promotion evaluation, invalidation policy execution, workflow replacement, or MCP graph exposure in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the base artifact record shape is too thin, later tasks will reintroduce parallel envelopes for lineage, invariants, and task references.
- If this task pulls slot binding or promotion policy into the foundation, the next tasks lose a clean layering boundary.
- If serialization is not explicit and stable, repository-local persistence will drift between call sites.
