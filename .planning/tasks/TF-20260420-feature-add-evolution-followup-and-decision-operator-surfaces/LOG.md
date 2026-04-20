# Log

## Timeline

- Created task through CLI fallback because the live MCP `sisyphus.request_task` runtime still resolved stale `src/taskflow/templates_data/...` paths.
- Narrowed the slice to operator-facing follow-up request and decision surfaces only.
- Added `evolution request-followup` and `evolution decide` CLI entrypoints without widening into plan approval, spec freeze, provider execution, or verify automation.
- Added `sisyphus.evolution_followup_request` and `sisyphus.evolution_decide` MCP tools with stable response payloads.
- Added operator-layer tests covering defaulted verification/evidence lineage, decision projection from follow-up task state, and actionable non-follow-up or missing-run failures.

## Notes

- Lower-level bridge, receipt projection, verification projection, promotion-gate, and decision-envelope logic already exist in the repository.
- This slice should surface that existing logic without bypassing the standard Sisyphus lifecycle.
- Operator surfaces now stop at review-gated task creation and decision recording. Normal task advancement still belongs to the standard Sisyphus lifecycle.

## Follow-ups

- Keep the active MCP runtime repair separate from this code change, even though the new MCP tools will also need a reconnect to become visible in the current session.
