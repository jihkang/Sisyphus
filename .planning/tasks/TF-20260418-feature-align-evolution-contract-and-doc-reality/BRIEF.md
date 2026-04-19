# Brief

## Task

- Task ID: `TF-20260418-feature-align-evolution-contract-and-doc-reality`
- Type: `feature`
- Slug: `align-evolution-contract-and-doc-reality`
- Branch: `feat/align-evolution-contract-and-doc-reality`

## Problem

- The current evolution package is still a read-only planning and scoring foundation, but some docs and names read ahead of that reality.
- If the contract types and docs are not aligned now, later implementation tasks will inherit misleading names and imply capabilities that do not exist yet.
- This task must align the type surface and docs without silently introducing future behavior.

## Desired Outcome

- The evolution slice has a stable minimum contract vocabulary for the next implementation steps.
- The docs clearly separate `currently implemented` from `planned / future work`.
- No doc implies that mutators, MCP evolution tools, approval flow, isolated executor, or promotion pipeline are already present.

## Acceptance Criteria

- [ ] The minimum contract names for the current and near-next slice are defined or refined: `EvolutionRunRequest`, `EvolutionRunStage`, `EvolutionRunResult`, `EvolutionStageFailure`, `EvolutionFollowupRequest`, `EvolutionArtifactRef`, `EvolutionPromotionCandidate`, and `EvolutionInvalidationRecord`.
- [ ] The docs explicitly distinguish what is implemented today from what is only planned.
- [ ] No current doc claims that mutators, MCP evolution tools, approval flow, isolated executor, or promotion pipeline already exist.

## Constraints

- Keep scope to contract and documentation alignment only.
- Do not implement candidate mutation, CLI or MCP ingress, harness execution, or promotion flow in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If names are defined too broadly, later tasks may imply behavior that is still out of scope.
- If future-only types are treated as implemented runtime objects, readers will assume missing modules are bugs rather than planned work.
- If docs stay ahead of reality, operator review and implementation sequencing will drift.
