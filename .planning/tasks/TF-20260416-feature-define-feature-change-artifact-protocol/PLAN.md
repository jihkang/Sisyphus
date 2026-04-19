# Plan

## Implementation Plan

1. Create a dedicated protocol document for `FeatureChangeArtifact` so the first composite artifact is defined in one stable place instead of remaining embedded in the architecture overview.
2. Specify the protocol in enough detail to lock slots, invariants, claim-based verification, promotion, invalidation, and reconstruction envelope structure.
3. Update the architecture overview and task docs so the new protocol becomes the canonical next design lock for future implementation.

## Risks

- The protocol must be specific enough to guide implementation without overclaiming that the current runtime already persists the full artifact graph.
- The first protocol needs to demonstrate both named and collection slot semantics, or it will fail to exercise the composition model the architecture now depends on.

## Test Strategy

### Normal Cases

- [x] `FeatureChangeArtifact` is documented as one coherent protocol with explicit slots and composition rules.

### Edge Cases

- [x] The protocol demonstrates both named slots and collection slots and distinguishes candidate, verified, promotable, and stale states.

### Exception Cases

- [x] The protocol explains how stale inputs and invariant failures should force reverify, reassemble, or reapproval instead of generic retry.

## Verification Mapping

- `FeatureChangeArtifact is documented as one coherent protocol with explicit slots and composition rules.` -> `manual review of docs/feature-change-artifact.md`
- `The protocol demonstrates both named slots and collection slots and distinguishes candidate, verified, promotable, and stale states.` -> `manual review of slot model and artifact state sections`
- `The protocol explains how stale inputs and invariant failures should force reverify, reassemble, or reapproval instead of generic retry.` -> `manual review of invariants and invalidation matrix sections`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
