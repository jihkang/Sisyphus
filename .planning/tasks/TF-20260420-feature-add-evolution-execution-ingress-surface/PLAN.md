# Plan

## Implementation Plan

1. Add a shared evolution ingress helper that calls `execute_evolution_run(...)`, normalizes optional `run_id`, `target_ids`, `task_ids`, and `max_events` inputs, and renders a stable reviewable response from the created run artifacts.
2. Expose that helper through CLI as `sisyphus evolution execute ...` without changing the existing persisted-run inspection commands.
3. Expose the same helper through MCP as `sisyphus.evolution_execute`, with a bounded schema and response that includes run identity, artifact directory, and rendered overview or failure details.
4. Add regression coverage for CLI and MCP success paths, explicit filtering inputs, and actionable error reporting while preserving the read-only boundary.
5. Update docs and verification notes to match the final ingress surface and scoped behavior.

## Risks

- The new execute surface could blur the distinction between read-only evolution evaluation and production follow-up execution if the response contract is not explicit.
- Wiring CLI and MCP separately could drift if they do not share a single ingress helper.
- Failure handling needs to surface `run_id` and artifact context without leaving the user with a generic traceback.

## Test Strategy

### Normal Cases

- [x] CLI and MCP can start a read-only evolution run and return reviewable metadata for the created run.

### Edge Cases

- [x] Explicit `target_ids`, `task_ids`, and `max_events` inputs flow through to the orchestrator without widening scope.
- [x] Existing `evolution run/status/report/compare` inspection commands remain unchanged for persisted runs.

### Exception Cases

- [x] Orchestrator failures surface actionable run and artifact context instead of a generic failure.
- [x] Duplicate or invalid run creation input fails without mutating live task state or creating follow-up execution side effects.

## Verification Mapping

- `CLI and MCP can start a read-only evolution run and return reviewable metadata for the created run.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_sisyphus tests.test_mcp_core tests.test_evolution`
- `Explicit target_ids, task_ids, and max_events inputs flow through to the orchestrator without widening scope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_sisyphus tests.test_mcp_core`
- `Orchestrator failures surface actionable run and artifact context instead of a generic failure.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_sisyphus tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
