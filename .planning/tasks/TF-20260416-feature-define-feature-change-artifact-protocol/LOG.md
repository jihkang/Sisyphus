# Log

## Timeline

- Created task
- Chose a dedicated protocol document instead of extending the architecture overview further so the first composite artifact can evolve independently.
- Defined `FeatureChangeArtifact` with explicit slot bindings, artifact states, composition rule, invariants, verification obligations, promotion gate, invalidation matrix, and a reconstruction envelope example.
- Updated `docs/architecture.md` so the protocol document is the canonical next design lock for the artifact-centric model.

## Notes

- This task changes documentation only. It does not claim the current runtime already persists full artifact records, slot bindings, or promotion decisions in the new schema.
- The protocol is intentionally concrete enough to guide the next storage-model or typed-model implementation pass.

## Follow-ups

- Define the repository-local schema or typed model layer that can store `FeatureChangeArtifact`, verification claims, slot bindings, promotion decisions, and invalidation records.
