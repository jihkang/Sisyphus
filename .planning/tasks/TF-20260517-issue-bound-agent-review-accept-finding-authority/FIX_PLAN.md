# Fix Plan

## Root Cause Hypothesis

- Agent-facing review and execution paths do not yet enforce a strict boundary between proposing findings, accepting work, and promoting artifacts.
- Context retrieval can help reduce hallucination only if downstream review and acceptance stages are forced to cite retrieved or verified evidence.

## Fix Strategy

1. Inventory current agent execution, review, conformance, verification, and promotion paths.
2. Define an authority matrix for proposer, reviewer, acceptor, invalidator, and promoter roles.
3. Add or update record schemas so findings and acceptance decisions carry source refs/evidence refs.
4. Require review findings to cite ContextPack items, task docs, artifacts, verification claims, or command receipts.
5. Require acceptance/promotion gates to evaluate explicit evidence and reject uncited claims.
6. Add regression tests for uncited finding rejection, role separation, and verified evidence promotion flow.

## Design Evaluation

- Design Mode: `full`
- Decision Reason: `changes review and promotion authority boundaries across agent, verification, and promotion layers`
- Confidence: `medium`
- Layer Impact: `layer-reshaping`
- Layer Decision Reason: `redefines authority flow between agent output, review findings, acceptance decisions, and promotion gates`
- Required Design Artifacts: `authority matrix, evidence contract, sequence diagram`

## Design Artifacts

- Connection Diagram: `pending`
- Sequence Diagram: `pending`
- Boundary Note: `pending`

## Test Strategy

### Normal Cases

- [ ] Evidence-cited review findings are accepted into the review record.
- [ ] Acceptance decisions pass when mapped obligations cite verified artifacts/receipts.
- [ ] Promotion remains eligible when execution, verification, review, and evidence refs align.

### Edge Cases

- [ ] Broad ContextPack evidence cannot override frozen task docs.
- [ ] Multiple reviewers can add findings without one model owning all authority.
- [ ] Superseded or stale evidence cannot satisfy a new acceptance decision.

### Exception Cases

- [ ] Uncited findings are rejected or marked non-authoritative.
- [ ] Acceptance without verification evidence fails closed.
- [ ] Promotion judgment fails when evidence refs point outside the current task/artifact lineage.

## Verification Mapping

- `Evidence-cited review findings are accepted` -> `targeted unit/integration test`
- `Acceptance decisions require verified artifacts/receipts` -> `targeted unit/integration test`
- `Promotion remains evidence-bound` -> `targeted promotion gate test`
- `Uncited findings are rejected` -> `targeted negative test`

## External LLM Review

- Required: `yes`
- Provider: `tbd`
- Purpose: `review authority matrix and evidence contract for hallucination and privilege-boundary risks`
- Trigger: `before implementation approval`
