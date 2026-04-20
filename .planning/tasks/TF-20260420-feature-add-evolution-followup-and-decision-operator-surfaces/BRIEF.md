# Brief

## Task

- Task ID: `TF-20260420-feature-add-evolution-followup-and-decision-operator-surfaces`
- Type: `feature`
- Slug: `add-evolution-followup-and-decision-operator-surfaces`
- Branch: `feat/add-evolution-followup-and-decision-operator-surfaces`

## Problem

- The repository already has internal follow-up bridging, receipt projection, verification projection, promotion-gate evaluation, and decision-envelope recording.
- Operator-facing surfaces still stop at `evolution execute` plus persisted-run inspection. There is no stable CLI/MCP path to request a review-gated follow-up task from a run or to evaluate and record the resulting promotion/invalidation decision from a follow-up task.
- The missing surface leaves the core evolution loop incomplete even though the lower-level logic already exists.

## Desired Outcome

- CLI and MCP can create a reviewable evolution follow-up task request from an executed run without bypassing normal Sisyphus review gates.
- CLI and MCP can evaluate and record a promotion or invalidation decision from an existing evolution follow-up task using the current receipt, verification, gate, and envelope logic.
- The slice stays bounded to operator surfaces and projection helpers. Actual plan approval, spec freeze, provider execution, and verify continue to run through the normal Sisyphus lifecycle.

## Acceptance Criteria

- [x] CLI adds a bounded follow-up request entrypoint that creates a reviewable Sisyphus follow-up task from an executed evolution run using the existing bridge contract.
- [x] CLI adds a bounded decision entrypoint that loads an existing evolution follow-up task, projects receipts and verification, evaluates the promotion gate, and records the resulting promotion or invalidation envelope.
- [x] MCP exposes equivalent tools for follow-up request and decision recording with stable response payloads.
- [x] Tests cover the success path, defaulted evidence/verification behavior, and actionable failures without widening into auto-approval or auto-execution.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not auto-approve plans, auto-freeze specs, auto-run providers for production changes, or auto-verify follow-up tasks in this slice.
- Keep stale MCP `sisyphus.request_task` runtime repair out of scope for this code change.
