# Brief

## Task

- Task ID: `TF-20260413-feature-evolution-core-control-plane`
- Type: `feature`
- Slug: `evolution-core-control-plane`
- Branch: `feat/evolution-core-control-plane`

## Problem

- The self-evolution plan in `docs/self-evolution-mcp-plan.md` defines a new control plane, but there is no `src/taskflow/evolution/` package yet.
- The next safe slice is not dataset execution or candidate mutation; it is the core model layer that names evolvable targets and describes a run without touching live task state.
- The implementation needs a stable foundation that later MCP tools/resources can expose.

## Desired Outcome

- `src/taskflow/evolution/` exists with a small, explicit public surface.
- A run can be represented as structured data in memory.
- Phase-1 safe text/policy targets are registered in one place and can be enumerated predictably.
- A runner skeleton can build an evolution run plan without writing files or mutating repository task state.

## Acceptance Criteria

- [x] A new `taskflow.evolution` package exists with exported run-model and registry interfaces.
- [x] The target registry contains only safe phase-1 text/policy targets for the first milestone.
- [x] A runner skeleton can resolve all default targets or an explicit subset and return a stable in-memory run model.
- [x] Focused tests cover target registration, target selection, and the non-mutating runner behavior.

## Constraints

- Keep scope to `evolution-core`; do not implement dataset extraction, candidate mutation, or MCP surface changes yet.
- Do not mutate live `.planning` task state from the evolution runner.
- Prefer clear dataclasses and explicit registry metadata over placeholder magic.
