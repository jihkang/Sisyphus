# Plan

## Implementation Plan

1. Align the replay task to the current artifact-model baseline so projection builds on the same artifact foundation and slot/claim vocabulary.
2. Add or confirm a dedicated projection module that maps feature-task runtime state into artifact views.
   - load task record and required docs
   - derive feature spec, implementation candidate, tests, and receipt/evidence artifacts
   - derive slot bindings and verification claims from the current task state
   - derive composite `FeatureChangeArtifact`-compatible envelope with lineage and task refs
3. Keep the projection read-only.
   - task state remains the live authority
   - artifact projection is a view/adaptation layer
   - no workflow mutation, no promotion routing, no MCP graph surface in this slice
4. Add focused regression tests and update task docs to match the actual projection boundary.

## Risks

- If the projection omits existing verify outputs or branch/base-branch metadata, later promotion/invalidation logic will lose key reconstructability inputs.
- If the projection assumes feature-task docs are always complete, it will fail opaquely instead of surfacing actionable adapter errors.
- If artifact IDs or task refs are unstable, later consumers will not be able to compare projections deterministically.

## Safety Invariants

- Projection is read-only and must not mutate task state, docs, or workflow fields.
- Tasks remain the live authority; artifact views are derived outputs.
- Projection must reuse the artifact foundation and slot/claim models rather than inventing parallel payload shapes.
- This task does not add promotion evaluation, invalidation routing, or MCP/UI exposure.

## Test Strategy

### Normal Cases

- [ ] A verified feature task projects into a reconstructable `FeatureChangeArtifact`-compatible envelope with lineage, slot bindings, and verification claims.
- [ ] A feature task with branch/base-branch metadata projects implementation and task-run refs deterministically.

### Edge Cases

- [ ] A pre-verify feature task still projects a candidate envelope with stable empty or pending verification sections instead of fabricating success.
- [ ] Projection remains stable when verify command output is absent but task docs and lifecycle metadata exist.

### Exception Cases

- [ ] Unsupported task types or missing required feature docs fail with actionable projection errors.

## Verification Mapping

- `A verified feature task projects into a reconstructable FeatureChangeArtifact-compatible envelope with lineage, slot bindings, and verification claims.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifact_projection`
- `A feature task with branch/base-branch metadata projects implementation and task-run refs deterministically.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifact_projection`
- `A pre-verify feature task still projects a candidate envelope with stable empty or pending verification sections instead of fabricating success.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifact_projection`
- `Unsupported task types or missing required feature docs fail with actionable projection errors.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifact_projection`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
