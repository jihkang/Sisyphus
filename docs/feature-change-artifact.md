# FeatureChangeArtifact Protocol

This document defines the first concrete composite artifact protocol for Sisyphus.

`FeatureChangeArtifact` is a contract-bearing composite object for repository change delivery. It represents not just "work happened", but "a feature change is materially assembled, verified, and eligible for promotion under recoverable rules".

## Purpose

`FeatureChangeArtifact` is the first protocol to lock because it matches the repository's existing workflow while forcing the system to define:

- role-based slots and collection slots
- cross-artifact invariants
- layered verification obligations
- promotion gates
- invalidation behavior
- a reconstructable envelope

It is the bridge between the current task-oriented runtime and the target artifact-centric work graph.

## Protocol Summary

`FeatureChangeArtifact` is valid only when it binds a feature spec, one or more implementation candidates, one selected implementation, relevant tests, supporting verification claims, and optional approvals into one reconstructable contract.

The protocol does not require that every slot be filled at every stage. It defines when the composite is only a candidate, when it is verified, and when it is promotable.

## Slot Model

The protocol intentionally uses both named slots and collection slots.

| Slot | Kind | Cardinality | Required For Promotion | Description |
| --- | --- | --- | --- | --- |
| `spec` | named | exactly 1 | yes | Canonical feature intent, scope, and acceptance criteria. |
| `implementation_candidates[]` | collection | 1..n | yes | Candidate implementations capable of satisfying the spec. |
| `selected_implementation` | named | 0..1 | yes | The implementation candidate currently bound as the promotable change. |
| `tests[]` | collection | 1..n | yes | Test artifacts covering normal, edge, exception, and regression obligations. |
| `verification_claims[]` | collection | 0..n | yes | Verification artifacts carrying local, cross, or composite claims and evidence. |
| `approvals[]` | collection | 0..n | policy-dependent | Human or policy approvals bound to the current candidate. |
| `execution_receipts[]` | collection | 0..n | yes | Receipts for the task runs, tool executions, and command invocations that produced or checked bound artifacts. |

## Artifact States

The protocol distinguishes composition state from execution failure.

| State | Meaning |
| --- | --- |
| `draft` | The composite exists, but required slots are not yet meaningfully bound. |
| `candidate` | A spec and at least one implementation candidate exist, but promotion obligations are not yet closed. |
| `verified` | Required verification claims for the current selected implementation are passing. |
| `promotable` | Verification, invariants, freshness, and approval policy are all satisfied. |
| `promoted` | The artifact has been accepted as the current authoritative feature change result. |
| `invalid` | The composite cannot currently satisfy its contract because required invariants or obligations are broken. |
| `stale` | The composite was previously valid but one or more bound inputs changed and invalidated some claims or decisions. |

## Composition Rule

The protocol's composition rule is:

> a `FeatureChangeArtifact` is satisfied when one feature spec, one selected implementation candidate, the required tests, the required verification claims, and the required approvals are bound under one consistent feature identity and one reconstructable repository lineage

This is a protocol-specific rule, not a universal composition rule for all artifact types.

## Invariants

The following invariants must hold for a promotable composite.

1. Every bound artifact counted by the composite must declare the same `feature_id`.
2. `selected_implementation` must reference one member of `implementation_candidates[]`.
3. Every test counted toward promotion must declare compatibility with the exact `spec` revision and the exact `selected_implementation` revision it is meant to check.
4. Every verification claim counted toward promotion must name the exact bound inputs it depends on, including the `spec`, `selected_implementation`, and any relevant test artifacts.
5. All bound artifacts must share a compatible repository lineage, including repository identity and base lineage or an explicitly recorded compatibility relation.
6. Ownership conflicts across the selected implementation and promoted test set must be absent or explicitly resolved in the envelope.

If an invariant fails, the composite is not retryable by default. It requires recomposition, redefinition, or an explicit resolution record.

## Verification Obligations

Verification is claim-based. Each claim must include:

- the claim being asserted
- the scope of the claim
- the exact artifact inputs it depends on
- evidence proving the claim

### Local Verification

Local verification checks artifacts in isolation.

- `spec` is structurally complete and not placeholder text
- each implementation candidate is internally valid as a change artifact
- each test artifact is internally valid and executable
- each verification artifact is well-formed and references real evidence

### Cross Verification

Cross verification checks relationships between artifacts.

- the selected implementation satisfies the current spec revision
- tests map to the current spec obligations
- verification claims reference the exact selected implementation and current tests
- approvals, if present, bind to the current candidate rather than a stale predecessor

### Composite Verification

Composite verification checks the higher-order contract.

- the requested feature behavior works end to end
- the selected implementation plus current tests and evidence satisfy the feature obligation as a whole
- no unresolved conflict or stale dependency blocks promotion
- the composite remains reviewable and reconstructable as one coherent change unit

Passing local verification does not imply passing cross or composite verification.

## Promotion Gate

A `FeatureChangeArtifact` becomes `promotable` only when all of the following are true:

1. `spec` is bound and complete.
2. `selected_implementation` is bound and belongs to `implementation_candidates[]`.
3. Required tests are bound for the spec's normal, edge, and exception obligations, or an explicit waiver artifact exists.
4. Required local, cross, and composite verification claims are all passing.
5. No stale input remains unresolved.
6. No unresolved ownership, merge, or lineage conflict remains.
7. Required approvals or policy waivers are present.
8. The reconstruction envelope is complete enough to replay why the artifact is valid.

Promotion is therefore obligation closure, not task completion.

## Invalidation Matrix

| Changed Input | What Becomes Stale | Required Action |
| --- | --- | --- |
| `spec` revision changes | selected implementation binding, tests compatibility, cross claims, composite claims, approvals | recompose, reverify cross/composite, reapprove if needed |
| new or changed implementation candidate | local verification for that candidate | verify locally; if selected, also reverify cross/composite |
| `selected_implementation` changes | prior cross claims, composite claims, approvals, promotion decision | reverify all dependent claims and rerun promotion gate |
| tests change | verification claims using those tests, composite status | reverify affected claims and reevaluate promotion |
| verification evidence changes | promotion status and any dependent summary | reevaluate gate and update envelope |
| approval policy changes | approval validity and promotion status | reapprove or record waiver |
| repository lineage or merge base changes | compatibility invariant, composite claims, promotion decision | reassemble or restage candidate, then reverify |

Invalidation happens before a change request. The system first marks stale dependencies and only then decides whether to reverify, reassemble, replan, or escalate.

## Reconstruction Envelope

Every `FeatureChangeArtifact` must carry an envelope that allows reconstruction of why the composite exists and why it is currently valid or stale.

The minimum fields are:

```json
{
  "artifact_id": "artifact-feature-change-001",
  "artifact_type": "feature_change",
  "feature_id": "feature/mobile-automation",
  "state": "promotable",
  "composition_rule": "feature_change/v1",
  "slot_bindings": {
    "spec": "artifact-spec-123",
    "implementation_candidates": ["artifact-impl-201", "artifact-impl-202"],
    "selected_implementation": "artifact-impl-202",
    "tests": ["artifact-test-310", "artifact-test-311"],
    "verification_claims": ["artifact-verify-401", "artifact-verify-402"],
    "approvals": ["artifact-approval-501"],
    "execution_receipts": ["receipt-601", "receipt-602"]
  },
  "lineage": {
    "repo_id": "jihkang/Sisyphus",
    "base_ref": "main@48d9ee4",
    "parent_artifacts": ["artifact-spec-123", "artifact-impl-202"],
    "producing_task_specs": ["task-spec-701"],
    "producing_task_runs": ["task-run-801", "task-run-802"]
  },
  "invariants": [
    {"id": "same-feature-id", "status": "passed"},
    {"id": "selected-is-candidate", "status": "passed"}
  ],
  "verification_summary": {
    "local": ["artifact-verify-401"],
    "cross": ["artifact-verify-402"],
    "composite": ["artifact-verify-403"]
  },
  "promotion": {
    "gate_version": "feature_change/v1",
    "decision": "promotable",
    "decided_at": "2026-04-16T17:00:00Z",
    "decided_by": "policy/manual"
  },
  "invalidation": {
    "stale_inputs": [],
    "required_actions": []
  }
}
```

The envelope does not replace payload artifacts. It explains the contract that makes the payload promotable.

## Mapping To Current Sisyphus Runtime

The current repository does not yet implement this artifact graph directly. The nearest existing runtime pieces are:

- task docs and `task.json` as partial spec and lifecycle records
- task worktrees and receipts as execution evidence
- verify outputs as early verification artifacts
- branch, PR, and merge operations as early promotion-adjacent decisions

This protocol should therefore be treated as the next design lock for future implementation, not as a claim that the runtime already persists all of these structures.

## Implementation Follow-Up

The next concrete step after this document is to define the storage shape for:

- artifact identifiers and typed artifact records
- slot-binding records
- verification claim records
- promotion decision records
- invalidation state

That work can start with a repository-local schema draft or typed Python model layer, but it should preserve this protocol unchanged unless the protocol itself is explicitly revised.
