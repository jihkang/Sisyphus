# Plan

## Implementation Plan

1. Inspect the current code path related to: Harden inbox events and split daemon boundaries.
2. Implement the requested behavior for: Implement the next repository-review remediation as one compatibility-preserving change. Introduce strict typed inbox event and payload models with explicit allow-lists, exact scalar/container type checks, bounded strings and collections, non-negative/positive integer constraints, safe relative changed-file paths, and JSON-serializable source_context. Move inbox persistence/claim/complete/fail mechanics behind an infra repository using existing atomic JSON persistence. Make malformed JSON, malformed schema, and unsupported event types isolated failures that are moved to the failed inbox, logged, counted, and never crash the daemon cycle or remain pending. Extract task brief/plan rendering from daemon.py into a domain task document module while preserving all existing daemon imports as compatibility aliases. Preserve the current public dict-shaped queue/process API and all valid-event behavior. Add focused unit tests for valid events, rejection classes, failure quarantine, atomic queue writes, continuation after a bad event, compatibility imports, and unchanged valid outputs. Run the full test suite, branch coverage gate, lock check, package build, Sisyphus verification, CI, PR, merge receipt, and close..
3. Update tests and task docs to match the final behavior.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Requested conversation workflow succeeds

### Edge Cases

- [ ] Minimal valid input still behaves predictably

### Exception Cases

- [ ] Unexpected failure surfaces an actionable error

## Verification Mapping

- `Requested conversation workflow succeeds` -> `sisyphus verify`
- `Minimal valid input still behaves predictably` -> `targeted regression test`
- `Unexpected failure surfaces an actionable error` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
