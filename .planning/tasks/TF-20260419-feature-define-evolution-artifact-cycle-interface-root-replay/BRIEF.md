# Brief

## Task

- Task ID: `TF-20260419-feature-define-evolution-artifact-cycle-interface-root-replay`
- Type: `feature`
- Slug: `define-evolution-artifact-cycle-interface-root-replay`
- Branch: `feat/define-evolution-artifact-cycle-interface-root-replay`

## Problem

- `TF-20260418-feature-define-evolution-artifact-cycle-interface` already defined and verified the artifact-cycle interface slice, but that task is blocked only because its stale task worktree predates the current root source-of-truth.
- The current root worktree now carries the active `taskflow` -> `sisyphus` migration baseline, so the artifact-cycle contract must be replayed on top of that adopted baseline rather than resumed in the old worktree.
- This follow-up task must preserve the original narrow boundary: the minimum evolution artifact-cycle interface only.

## Desired Outcome

- The repository has a minimum artifact vocabulary for the evolution slice that is sufficient for orchestration, evidence capture, and later promotion/invalidation on top of the current root-adopted baseline.
- Each artifact kind has defined ownership, minimum fields, and a role in reconstruction.
- The artifact interface remains intentionally narrow and does not prematurely turn into a universal artifact engine.

## Acceptance Criteria

- [ ] The artifact kinds are defined for the current vertical slice: `EvolutionRunSpec`, `EvolutionDatasetArtifact`, `EvolutionCandidateArtifact`, `EvolutionEvaluationArtifact`, `EvolutionReportArtifact`, `EvolutionFollowupRequestArtifact`, `ExecutionReceiptArtifact`, `VerificationArtifact`, and `PromotionDecisionArtifact`.
- [ ] Each artifact kind documents minimum reconstructability fields such as identifier, kind, producing stage, dependencies, evidence references, and status.
- [ ] Ownership boundaries between evolution-generated artifacts and Sisyphus-authoritative artifacts are explicit.

## Constraints

- Keep scope to the artifact-cycle interface and model surface.
- Do not implement a generic repository-wide artifact engine in this task.
- Do not add runtime surface APIs in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the artifact interface is too generic, later work will stall behind an unnecessary platform rewrite.
- If the artifact interface is too shallow, later tasks will not have enough evidence or dependency fields for reconstruction.
- If ownership is unclear, evolution-generated artifacts and Sisyphus receipts can be conflated.
