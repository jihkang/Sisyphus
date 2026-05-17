# Plan

## Implementation Plan

1. Inventory existing SearchDocument metadata, artifact snapshot freshness, verification claims, and promotion receipts.
2. Define authority tiers for task docs, frozen specs, artifact snapshots, verification claims, promotion receipts, and unavailable/stale evidence.
3. Add projection metadata for authority tier and reason where missing.
4. Update lexical scoring to combine term score with authority/freshness boosts and demotions.
5. Render authority reason fields in ContextPack items.
6. Add ranking tests for fresh verified evidence vs stale/draft evidence.

## Risks

- Overweighting authority can hide relevant low-authority evidence that should still be visible as supporting context.
- Authority metadata may be incomplete for legacy tasks.
- Ranking policy may need later DAG validation for supersedes/contradicts edges.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `extends existing retrieval read model with authority policy`
- Confidence: `medium`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `changes retrieval ranking and ContextPack metadata without changing lifecycle authority`
- Required Design Artifacts: `ranking policy table`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `ranking policy table pending during implementation`

## Test Strategy

### Normal Cases

- [ ] Fresh verified artifact/claim ranks above draft task text for equivalent lexical matches.
- [ ] ContextPack item includes authority tier and selection reason.

### Edge Cases

- [ ] Legacy documents without authority metadata still rank deterministically.
- [ ] Stale snapshots remain visible but demoted.
- [ ] Empty query behavior remains unchanged.

### Exception Cases

- [ ] Malformed authority metadata fails or normalizes actionably.
- [ ] Unavailable evidence cannot satisfy a high-authority filter.

## Verification Mapping

- `Authority scoring` -> `python -m unittest tests.test_search_context -v`
- `Artifact freshness metadata` -> `python -m unittest tests.test_artifact_projection tests.test_artifact_evaluator -v`
- `ContextPack metadata rendering` -> `python -m unittest tests.test_search_context.SearchContextTests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
