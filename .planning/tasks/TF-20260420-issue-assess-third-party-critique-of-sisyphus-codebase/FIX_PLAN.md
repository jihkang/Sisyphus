# Fix Plan

## Root Cause Hypothesis

- The behavior described by the request likely originates in the code path for: Assess third-party critique of Sisyphus codebase.

## Fix Strategy

1. Keep this issue as the umbrella parent for critique-backed follow-up work instead of treating it as the direct implementation vehicle.
2. Split the concrete gaps into feature and issue tasks that can be reviewed and executed independently.
3. Record the parent/child and blocking/parallel relationships here until Sisyphus grows first-class task DAG state.
4. Execute follow-up work in dependency order and use this issue to track whether the critique has been structurally resolved.

## Task Graph

### Parent Nodes

- `TF-20260421-feature-repair-mcp-resource-discovery-and-schema-contract`
  - Parent kind: `contract`
  - Blocking level: `hard blocker`
  - Purpose: stabilize MCP resource/schema discovery and the canonical state surface
- `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Parent kind: `promotion schema`
  - Blocking level: `hard blocker`
  - Purpose: define first-class promotion state before executor and stacked PR work
- `TF-20260421-issue-measure-mcp-and-promotion-value`
  - Parent kind: `evaluation`
  - Blocking level: `observer`
  - Purpose: measure whether the extra ceremony pays off

### Child Relationships

- `TF-20260421-feature-normalize-task-state-projections`
  - Parent: `TF-20260421-feature-repair-mcp-resource-discovery-and-schema-contract`
  - Depends on: `TF-20260421-feature-repair-mcp-resource-discovery-and-schema-contract`
  - Blocking level: `hard blocker`
- `TF-20260421-feature-promotable-change-classification`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Blocking level: `hard blocker`
- `TF-20260421-feature-close-gated-by-promotion`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Blocking level: `hard blocker`
- `TF-20260421-feature-git-promotion-executor`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on:
    - `TF-20260421-feature-promotion-state-machine-and-task-schema`
    - `TF-20260421-feature-promotable-change-classification`
  - Blocking level: `hard blocker`
- `TF-20260421-feature-promotion-receipt-handoff-and-close`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on:
    - `TF-20260421-feature-close-gated-by-promotion`
    - `TF-20260421-feature-git-promotion-executor`
  - Blocking level: `hard blocker`
- `TF-20260421-feature-stacked-pr-base-resolution`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on:
    - `TF-20260421-feature-promotion-state-machine-and-task-schema`
    - `TF-20260421-feature-git-promotion-executor`
  - Blocking level: `late-stage blocker`
- `TF-20260421-feature-parent-merge-retarget-and-reverify`
  - Parent: `TF-20260421-feature-promotion-state-machine-and-task-schema`
  - Depends on:
    - `TF-20260421-feature-stacked-pr-base-resolution`
    - `TF-20260421-feature-promotion-receipt-handoff-and-close`
  - Blocking level: `late-stage blocker`

## Recommended Execution Order

1. `TF-20260421-feature-repair-mcp-resource-discovery-and-schema-contract`
2. `TF-20260421-feature-normalize-task-state-projections`
3. `TF-20260421-feature-promotion-state-machine-and-task-schema`
4. `TF-20260421-feature-promotable-change-classification`
5. `TF-20260421-feature-close-gated-by-promotion`
6. `TF-20260421-feature-git-promotion-executor`
7. `TF-20260421-feature-promotion-receipt-handoff-and-close`
8. `TF-20260421-feature-stacked-pr-base-resolution`
9. `TF-20260421-feature-parent-merge-retarget-and-reverify`

## Parallel Work

- `TF-20260421-issue-measure-mcp-and-promotion-value`
  - Can run in parallel as soon as contract/schema vocabulary is stable enough to emit metrics
  - Should not block MVP promotion wiring unless measurement hooks require schema additions

## Open Limitation

- Sisyphus still lacks first-class `parent_task_id` and `depends_on` fields in canonical task state.
- Until that exists, this document is the source of truth for the current roadmap DAG.

## Test Strategy

### Normal Cases

- [x] The critique is translated into a stable umbrella roadmap with explicit parent and child work items

### Edge Cases

- [x] Contract, promotion schema, and measurement work are separated so observer tasks do not block implementation by accident

### Exception Cases

- [x] The roadmap notes the current schema limitation instead of pretending task DAG support already exists

## Verification Mapping

- `The critique is translated into a stable umbrella roadmap with explicit parent and child work items` -> `manual review`
- `Contract, promotion schema, and measurement work are separated so observer tasks do not block implementation by accident` -> `manual review`
- `The roadmap notes the current schema limitation instead of pretending task DAG support already exists` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
