# Brief

## Task

- Task ID: `TF-20260421-feature-repair-mcp-resource-discovery-and-schema-contract`
- Type: `feature`
- Slug: `repair-mcp-resource-discovery-and-schema-contract`
- Branch: `feat/repair-mcp-resource-discovery-and-schema-contract`

## Problem

- Repair MCP resource discovery and schema contract
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Stabilize MCP resource listing, schema discovery, and reference surface so stale templates or invalid URIs do not break repository-wide resource discovery. Ensure task record, task conformance, and MCP resources project consistent canonical state.

## Desired Outcome

- MCP resource discovery separates concrete resources from URI templates without assuming only `task://<task-id>` patterns exist.
- Missing but listed resources return stable placeholders instead of breaking discovery or reads before later lifecycle stages materialize them.
- Task and evolution resource surfaces expose a consistent markdown/JSON contract to MCP clients.

## Acceptance Criteria

- [x] Template discovery recognizes generic placeholder tokens such as `task://<task-id>/...` and `evolution://<run-id>/...`.
- [x] Invalid or stale URI definitions are skipped during resource/template discovery instead of crashing the server surface.
- [x] `task://<task-id>/repro` is listed in the MCP schema and task/evolution markdown resources use the correct MIME contract.
- [x] `promotion`, `changeset`, and feature artifact resources return stable placeholder or unavailable payloads when lifecycle state is incomplete.
- [x] Verification notes record the targeted MCP regression suite that passed.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
