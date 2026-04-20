# Plan

## Implementation Plan

1. Add shared projection helpers that can reconstruct an `EvolutionFollowupRequestArtifact` from a follow-up task record and derive the minimum gate inputs from persisted run artifacts plus task source context.
2. Expose a bounded follow-up request surface through CLI and MCP that calls the existing bridge contract with operator-supplied title/summary plus defaulted evidence and verification obligations when the operator does not override them.
3. Expose a bounded decision surface through CLI and MCP that loads an existing evolution follow-up task, projects execution and verification evidence, evaluates the promotion gate, and records the resulting promotion or invalidation envelope.
4. Add regression tests for request and decision success paths, default behavior, and actionable failure reporting.
5. Update docs to reflect that operator surfaces now cover read-only run execution, review-gated follow-up request creation, and decision recording, while normal lifecycle execution remains in standard Sisyphus commands/tools.

## Risks

- Surface helpers could accidentally blur the authority boundary if they start auto-advancing plan/spec/verify state instead of only requesting or evaluating.
- Reconstructing follow-up artifacts from task metadata must stay stable enough that future decision evaluation does not depend on in-memory bridge return values.
- The operator surface should default enough evidence and verification metadata to stay usable without hiding important inputs.

## Test Strategy

### Normal Cases

- [ ] CLI and MCP can request a review-gated evolution follow-up task from an executed run and receive stable lineage metadata back.
- [ ] CLI and MCP can evaluate an executed follow-up task into a promotion or invalidation decision using current receipts and verification artifacts.

### Edge Cases

- [ ] Minimal follow-up request input defaults evidence and verification obligations from the originating run without widening scope.
- [ ] Decision evaluation fails clearly when the task is not an evolution follow-up task or when the originating run artifacts are missing.

### Exception Cases

- [ ] Decision evaluation surfaces actionable blocker or lineage errors instead of recording a misleading envelope.
- [ ] Follow-up request creation rejects unsupported gate overrides or malformed evidence input without creating a task.

## Verification Mapping

- `CLI and MCP can request a review-gated evolution follow-up task from an executed run and receive stable lineage metadata back.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution tests.test_sisyphus tests.test_mcp_core tests.test_mcp_adapter`
- `CLI and MCP can evaluate an executed follow-up task into a promotion or invalidation decision using current receipts and verification artifacts.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution tests.test_sisyphus tests.test_mcp_core tests.test_mcp_adapter`
- `Minimal follow-up request input defaults evidence and verification obligations from the originating run without widening scope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution tests.test_sisyphus`
- `Decision evaluation surfaces actionable blocker or lineage errors instead of recording a misleading envelope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution tests.test_sisyphus`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
