# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current local baseline so the contract alignment work would apply to the current `sisyphus` naming surface.
- Added the minimum evolution contract vocabulary to the public API in `src/taskflow/evolution/runner.py` and exported it through `sisyphus.evolution`.
- Rewrote the evolution architecture docs so the current read-only slice is separated from near-next scaffolding and future work.

## Notes

- `EvolutionRunRequest` and `EvolutionRunStage` now describe the current run-planning slice explicitly instead of leaving the vocabulary implicit in function arguments and free-form strings.
- `EvolutionRunResult`, `EvolutionStageFailure`, `EvolutionArtifactRef`, `EvolutionFollowupRequest`, `EvolutionPromotionCandidate`, and `EvolutionInvalidationRecord` are now defined as near-next contracts without implying that runtime support already exists.
- `docs/architecture.md` and `docs/self-evolution-mcp-plan.md` now distinguish current behavior from future executor, MCP, promotion, and handoff work.

## Follow-ups

- Implement the artifact cycle and read-only orchestrator on top of the newly fixed contract vocabulary.
- Keep future executor, MCP, and promotion tasks aligned to these contract names instead of introducing parallel naming.
