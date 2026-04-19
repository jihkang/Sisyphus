# Brief

## Task

- Task ID: `TF-20260416-feature-implement-slot-binding-and-verification-claims`
- Type: `feature`
- Slug: `implement-slot-binding-and-verification-claims`
- Branch: `feat/implement-slot-binding-and-verification-claims`

## Problem

- The `FeatureChangeArtifact` protocol already defines named slots, collection slots, and claim-based verification, but the repository still lacks typed models for binding those concepts into a reconstructable envelope.
- Without explicit slot-binding and verification-claim records, later runtime projection and promotion tasks will either invent parallel ad hoc shapes or overload the base artifact record layer.
- This task needs to add the contract layer that sits on top of the artifact-record foundation and below runtime projection or policy evaluation.

## Desired Outcome

- Sisyphus has typed models for named-slot bindings, collection-slot bindings, verification claims, claim scope, dependency refs, and evidence refs aligned to `FeatureChangeArtifact`.
- The new models serialize and deserialize cleanly on top of the base artifact record layer.
- The result stays scoped to schema/model work plus focused tests and does not yet evaluate promotion policy or replace the live task workflow.

## Acceptance Criteria

- [ ] Introduce typed models for named-slot bindings and collection-slot bindings that can persist role-bearing and collection-bearing input relationships.
- [ ] Introduce a typed verification-claim model that records claim text, verification scope, dependency refs, and evidence refs.
- [ ] The model layer can represent the `FeatureChangeArtifact` protocol slots such as `spec`, `implementation_candidates[]`, `selected_implementation`, `tests[]`, and `verification_claims[]` without introducing promotion or invalidation policy yet.
- [ ] Focused tests cover round-trip serialization, mixed named/collection bindings, deterministic ordering, and malformed claim/binding payload errors.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep scope to schema/model plus focused tests.
- Do not add promotion policy, invalidation policy, runtime projection, workflow replacement, or MCP graph exposure in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If slot binding is too loosely typed, the later runtime projection task will leak task.json semantics into the artifact layer.
- If verification claims do not name scope, dependencies, and evidence explicitly, later promotion decisions will not be reconstructable.
- If this task folds policy evaluation into the schema layer, the promotion/invalidation evaluator task loses a clear boundary.
