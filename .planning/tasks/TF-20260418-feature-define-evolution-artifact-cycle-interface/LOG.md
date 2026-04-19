# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current local baseline so the artifact-cycle interface would apply to the current evolution slice.
- Added an explicit `artifacts.py` module for the evolution vertical slice and exported the new artifact contracts through `sisyphus.evolution`.
- Refactored the artifact models to share a private `_EvolutionArtifact` base so the public contract stays explicit without repeating the common reconstruction fields in every class.
- Updated `docs/architecture.md` and `docs/self-evolution-mcp-plan.md` so artifact ownership and reconstructability are documented before runtime orchestration expands.

## Notes

- Defined the minimum evolution-owned artifacts: `EvolutionRunSpec`, `EvolutionDatasetArtifact`, `EvolutionCandidateArtifact`, `EvolutionEvaluationArtifact`, `EvolutionReportArtifact`, and `EvolutionFollowupRequestArtifact`.
- Defined the Sisyphus-authoritative artifacts that sit on the same vertical slice: `ExecutionReceiptArtifact`, `VerificationArtifact`, and `PromotionDecisionArtifact`.
- Locked the minimum reconstructability fields for this slice to `artifact_id`, `kind`, `owner`, `producing_stage`, `status`, `depends_on`, `evidence_refs`, and `persisted`.
- Kept the interface narrow and explicitly documented that not all artifact kinds are already persisted at runtime.

## Follow-ups

- Use these artifact types when defining the read-only orchestrator and stage-transition contract.
- Attach runtime persistence and receipt generation only in the later executor and bridge tasks.
