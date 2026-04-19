# Brief

## Task

- Task ID: `TF-20260416-feature-define-feature-change-artifact-protocol`
- Type: `feature`
- Slug: `define-feature-change-artifact-protocol`
- Branch: `feat/define-feature-change-artifact-protocol`

## Problem

- define feature change artifact protocol
- Original request: Define the first concrete composite artifact protocol for Sisyphus: FeatureChangeArtifact. Specify its slots, invariants, verification obligations, promotion gate, invalidation matrix, and reconstruction envelope fields, and integrate that protocol into repository documentation as the next concrete architecture lock.

## Desired Outcome

- The repository docs define `FeatureChangeArtifact` as a concrete composite artifact protocol rather than only naming it abstractly.
- The protocol is specific enough to guide a future schema or model implementation without pretending the runtime already stores the full graph natively.

## Acceptance Criteria

- [x] A dedicated protocol document defines `FeatureChangeArtifact` slots, invariants, verification obligations, promotion gate, invalidation matrix, and reconstruction envelope fields.
- [x] `docs/architecture.md` points to the protocol as the first concrete design lock.
- [x] The task docs reflect the actual documentation scope and verification approach.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
