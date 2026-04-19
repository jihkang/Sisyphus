# Plan

## Implementation Plan

1. Re-read the existing architecture and evolution docs and collect every current sentence that assigns authority to `evolution`, `Sisyphus`, the harness executor, or read-only orchestration.
2. Replace ambiguous or descriptive wording with normative contract language.
   - `evolution` owns soft-cognition work only.
   - `Sisyphus` owns hard-state authority only.
   - The harness executor is evaluation-only.
   - Follow-up execution may be requested by evolution but may not be self-approved by evolution.
   - Read-only orchestration may persist append-only run artifacts only under `.planning/evolution/runs/<run_id>/`.
3. Make the boundary visible in both the general architecture doc and the evolution-specific doc so later implementation tasks inherit one consistent contract.
4. Update task docs and verification notes to reflect the final language and review scope.

## Hard Risks

- If authority ownership stays ambiguous, later executor and bridge tasks can bypass Sisyphus review gates by accident.
- If the harness executor is described too broadly, it can be treated as a general-purpose mutation executor rather than an evaluation device.
- If read-only is defined too narrowly, later tasks may refuse to persist run artifacts; if defined too loosely, later tasks may mutate live state.

## Safety Invariants

- `evolution` must not be documented as owning plan approval, spec freeze, promotion recording, or production execution.
- The harness executor must be documented as evaluation-only.
- Read-only orchestration must not be documented as mutating `src/`, `templates/`, or `.planning/tasks/<live_task_id>/`.
- Promotion and invalidation must be documented as hard-state decisions recorded through Sisyphus or explicit receipt envelopes.

## Out Of Scope

- Runtime implementation changes.
- Candidate mutation or materialization.
- CLI or MCP evolution surface additions.
- Promotion flow or bridge execution.

## Evidence Requirements

- Updated normative language in [docs/architecture.md](/Users/jihokang/Documents/Sisyphus/docs/architecture.md:1).
- Updated evolution-specific boundary language in [docs/self-evolution-mcp-plan.md](/Users/jihokang/Documents/Sisyphus/docs/self-evolution-mcp-plan.md:1).
- Task docs reflect the same boundary without contradictory wording.

## Failure And Recovery

- If the docs disagree on authority ownership, stop and revise the wording before plan approval.
- If the boundary implies new runtime behavior, move that behavior into a follow-up implementation task instead of expanding this task.

## Test Strategy

### Normal Cases

- [ ] The docs present one consistent authority model for `evolution`, the harness executor, and Sisyphus.

### Edge Cases

- [ ] Read-only orchestration is defined precisely enough to allow append-only run artifacts without permitting live-state mutation.

### Exception Cases

- [ ] No sentence in the docs allows evolution to approve, freeze, or promote its own follow-up work.

## Verification Mapping

- `The docs present one consistent authority model for evolution, the harness executor, and Sisyphus.` -> `manual review of docs/architecture.md and docs/self-evolution-mcp-plan.md`
- `Read-only orchestration is defined precisely enough to allow append-only run artifacts without permitting live-state mutation.` -> `manual review of updated boundary language`
- `No sentence in the docs allows evolution to approve, freeze, or promote its own follow-up work.` -> `manual review of updated boundary language`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
