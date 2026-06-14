# Plan

## Implementation Plan

1. [x] Add `src/sisyphus/evidence_graph.py` with schema constants, build/read/write helpers, summary projection, and closeout gate collection.
2. [x] Extend `run_verify` to write `artifacts/evidence/evidence-graph.json` after verification status and command results are known.
3. [x] Extend `run_close` to block newly verified tasks when evidence is missing, invalid, unsupported at high importance, or has blocking gaps.
4. [x] Expose evidence state through observation and `task://<task-id>/evidence`.
5. [x] Add regression tests for supported, partial, missing, unsupported, verify integration, closeout gates, and MCP resource exposure.

## Risks

- Over-gating legacy/manual verified tasks would break existing task closeout tests; evidence is required only when a task has a new `last_verified_at`.
- The initial evidence graph is deterministic and intentionally conservative; richer diff/spec linking can be added later.
- `VERIFY.md` remains a projection, so structured evidence must not rely on parsing prose.

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

- [x] Passing verify writes a supported evidence graph.

### Edge Cases

- [x] Partial medium-importance evidence does not block closeout.
- [x] Legacy/manual verified tasks without explicit evidence requirement are not evidence-gated.

### Exception Cases

- [x] Missing evidence graph blocks close for newly verified tasks.
- [x] Unsupported high-importance evidence blocks close.

## Verification Mapping

- `Passing verify writes a supported evidence graph` -> `tests.test_sisyphus.SisyphusVerifyTests`
- `Partial medium-importance evidence does not block closeout` -> `tests.test_evidence_graph`
- `Legacy/manual verified tasks without explicit evidence requirement are not evidence-gated` -> `tests.test_evidence_graph`
- `Missing evidence graph blocks close for newly verified tasks` -> `tests.test_sisyphus.SisyphusVerifyTests`
- `Unsupported high-importance evidence blocks close` -> `tests.test_evidence_graph`, `tests.test_sisyphus.SisyphusVerifyTests`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
