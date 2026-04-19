# Brief

## Task

- Task ID: `TF-20260415-feature-plan-automated-evolution-progression`
- Type: `feature`
- Slug: `plan-automated-evolution-progression`
- Branch: `feat/plan-automated-evolution-progression`

## Problem

- The evolution package now has the main read-only building blocks, but they still stop at individually invoked functions.
- `runner.py` only plans an evolution run and does not orchestrate dataset extraction, harness execution, constraints, fitness, and report generation as one controlled flow.
- Original request: Plan the next slice for Sisyphus evolution so that the evolution flow can progress automatically instead of stopping at individually-invoked steps. Focus on an implementation plan for orchestrating dataset build, harness execution, constraints, fitness, and report generation in a controlled runner.

## Desired Outcome

- `src/taskflow/evolution/runner.py` owns a single-run orchestration path that can progress from run planning through report generation without mutating live task state.
- The orchestration path composes the existing dataset, harness, constraints, fitness, and report modules instead of re-implementing them.
- The first automation slice remains operator-invoked and read-only; it does not add candidate mutation, MCP evolution tools/resources, or branch materialization yet.

## Acceptance Criteria

- [ ] A concrete implementation plan exists for a controlled `execute_evolution_run(...)` style orchestration entrypoint.
- [ ] The plan defines lifecycle stages, injected checks, failure handling, and output shape for automated progression.
- [ ] The plan keeps scope limited to read-only automation over existing evolution modules.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Keep evolution separate from the live Sisyphus task workflow.
- Do not introduce live task-state mutation, candidate mutation, or approval/branch flows in this slice.
