# Plan

## Implementation Plan

1. Align the task branch to the current local artifact-model baseline so slot bindings and claims build on top of the same durable record vocabulary.
2. Add a dedicated schema/model module for slot and claim records.
   - named-slot binding record
   - collection-slot binding record
   - slot-binding aggregate for `FeatureChangeArtifact`
   - verification-claim record
   - claim dependency refs and evidence refs
3. Keep the schema aligned to the `FeatureChangeArtifact` protocol without adding evaluation logic.
   - support `spec`
   - support `implementation_candidates[]`
   - support `selected_implementation`
   - support `tests[]`
   - support `verification_claims[]`
4. Add focused regression coverage and update task docs to reflect the schema boundary precisely.

## Risks

- If slot bindings are modeled as generic dict bags, later runtime projection will not be able to validate or reconstruct artifact roles deterministically.
- If verification claims do not separate scope, dependency refs, and evidence refs, policy evaluation will blur proof inputs with later decisions.
- If ordering is unstable for collection slots, persisted envelopes will drift across round-trips and make diffs noisy.

## Safety Invariants

- Named slots and collection slots stay distinct in the schema.
- Verification claims are proof records, not promotion decisions.
- Claim dependencies and evidence refs must remain explicit typed references.
- This task does not add promotion evaluation, invalidation routing, runtime projection, or workflow mutation.

## Test Strategy

### Normal Cases

- [ ] A `FeatureChangeArtifact`-style binding set can round-trip named slots and collection slots with deterministic ordering.
- [ ] A verification claim can round-trip claim text, scope, dependency refs, and evidence refs on top of the artifact foundation.

### Edge Cases

- [ ] Empty collection slots remain stable and serializable without collapsing into malformed null-heavy payloads.
- [ ] Mixed named-slot and collection-slot bindings preserve declared order for collection entries and claim dependencies.

### Exception Cases

- [ ] Missing required slot metadata or malformed verification-claim payloads fail with actionable validation errors.

## Verification Mapping

- `A FeatureChangeArtifact-style binding set can round-trip named slots and collection slots with deterministic ordering.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `A verification claim can round-trip claim text, scope, dependency refs, and evidence refs on top of the artifact foundation.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `Empty collection slots remain stable and serializable without collapsing into malformed null-heavy payloads.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`
- `Missing required slot metadata or malformed verification-claim payloads fail with actionable validation errors.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_artifacts`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
