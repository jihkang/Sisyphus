# Plan

## Implementation Plan

1. Inventory the current evolution code surface and the evolution-related docs to determine which names already exist and which names are still only proposed.
2. Define or refine the minimum contract vocabulary that the next implementation slices will depend on without introducing implied runtime behavior.
3. Rewrite the evolution docs so they explicitly separate current implementation from future work.
4. Add or adjust tests and task docs so the contract names and doc claims stay locked to the real codebase state.

## Hard Risks

- If contract names imply behavior that does not exist, later tasks will be planned against a fictitious runtime.
- If the docs still claim future components are implemented, operator review will not catch real scope gaps.
- If the contract surface is too narrow, later tasks will rename types again and create unnecessary churn.

## Safety Invariants

- This task may refine names and docs, but it must not imply execution behavior that is not yet implemented.
- `Currently implemented` and `planned / future work` must remain visibly separate.
- No contract name may be described as authoritative runtime state unless the current code actually stores or enforces it.

## Out Of Scope

- Candidate mutation.
- Isolated harness execution.
- CLI or MCP evolution ingress.
- Promotion, invalidation, or follow-up bridge execution.

## Evidence Requirements

- Updated evolution contract surface in `src/sisyphus/evolution`.
- Updated docs in [docs/self-evolution-mcp-plan.md](/Users/jihokang/Documents/Sisyphus/docs/self-evolution-mcp-plan.md:1) and [docs/architecture.md](/Users/jihokang/Documents/Sisyphus/docs/architecture.md:1).
- Regression coverage in [tests/test_evolution.py](/Users/jihokang/Documents/Sisyphus/tests/test_evolution.py:1) for any new or renamed contract types.

## Failure And Recovery

- If a proposed contract type cannot be grounded in current code or near-next slices, demote it to documented future work instead of exposing it as active runtime API.
- If the docs and code disagree after renaming, revise the docs before plan approval rather than leaving drift for follow-up tasks.

## Test Strategy

### Normal Cases

- [ ] The contract names used in code and docs consistently describe the current read-only evolution slice.

### Edge Cases

- [ ] Future-only items remain documented as planned work instead of being silently promoted to current behavior.

### Exception Cases

- [ ] The contract cleanup does not accidentally broaden scope into executor, CLI/MCP, or promotion work.

## Verification Mapping

- `The contract names used in code and docs consistently describe the current read-only evolution slice.` -> `targeted unit test in tests.test_evolution`
- `Future-only items remain documented as planned work instead of being silently promoted to current behavior.` -> `manual review of docs/self-evolution-mcp-plan.md and docs/architecture.md`
- `The contract cleanup does not accidentally broaden scope into executor, CLI/MCP, or promotion work.` -> `manual review of changed files`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
