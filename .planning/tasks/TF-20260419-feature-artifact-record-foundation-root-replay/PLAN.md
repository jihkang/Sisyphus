# Plan

## Implementation Plan

1. Align the replay task to the current root-adopted baseline so the artifact foundation is defined in the canonical `sisyphus` tree rather than an older task worktree snapshot.
2. Add or confirm a dedicated artifact model module in the canonical `sisyphus` package for durable artifact records.
   - `ArtifactRef`
   - `TaskSpecRef`
   - `TaskRunRef`
   - `ArtifactLineage`
   - `ArtifactInvariantRecord`
   - `ArtifactRecord`
   - `CompositeArtifactRecord`
3. Define a stable serialization contract.
   - each model exposes a deterministic `to_dict()`
   - record constructors or helpers can rebuild typed objects from serialized mappings
   - composite records keep reconstruction-envelope data explicit instead of flattening lineage and invariants into untyped dicts
4. Keep the scope aligned to the original slice.
   - preserve artifact refs, task refs, lineage, and invariant results
   - keep slot binding, verification claims, promotion decisions, and invalidation logic out of scope
5. Add focused regression coverage and update task docs to reflect the replay boundary precisely.

## Risks

- If the model couples itself to current task workflow details, later projection work will be forced to mirror `task.json` instead of building a reusable artifact layer.
- If serialization omits typed envelope fields, reconstructability will be lost before the projection task starts.
- If composite records do not clearly separate payload identity from envelope identity, later promotion and invalidation logic will blur the contract boundary.

## Safety Invariants

- Artifact records are durable state objects, not live workflow controllers.
- Task specs and task runs appear only as typed references inside lineage or envelope fields.
- Composite artifact records preserve reconstruction data explicitly: child artifact refs, task refs, lineage, composition rule, and invariant results.
- This task does not introduce promotion evaluation, invalidation routing, or MCP/UI behavior.

## Test Strategy

### Normal Cases

- [ ] A minimal artifact record with lineage and evidence refs round-trips through serialization and deserialization.
- [ ] A composite artifact record preserves child artifacts, task refs, lineage, composition rule, and invariant results in one reconstructable envelope.

### Edge Cases

- [ ] Optional lineage, evidence refs, or invariant collections stay empty-but-stable instead of becoming malformed null-heavy payloads.
- [ ] Record ordering for child refs and task refs remains deterministic after serialization.

### Exception Cases

- [ ] Missing required identity fields or malformed reconstruction data fail with actionable validation errors.

## Verification Mapping

- `A minimal artifact record with lineage and evidence refs round-trips through serialization and deserialization.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `A composite artifact record preserves child artifacts, task refs, lineage, composition rule, and invariant results in one reconstructable envelope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `Optional lineage, evidence refs, or invariant collections stay empty-but-stable instead of becoming malformed null-heavy payloads.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `Missing required identity fields or malformed reconstruction data fail with actionable validation errors.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
