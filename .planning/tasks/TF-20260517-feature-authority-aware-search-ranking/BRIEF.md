# Brief

## Task

- Task ID: `TF-20260517-feature-authority-aware-search-ranking`
- Type: `feature`
- Slug: `authority-aware-search-ranking`
- Branch: `feat/authority-aware-search-ranking`
- Backlog Order: `4/5`

## Problem

- Current lexical retrieval can return draft, stale, unavailable, or superseded task evidence without enough authority weighting.
- ContextPack consumers can see source refs and freshness, but ranking does not yet encode Sisyphus authority rules strongly enough.
- Without authority-aware ranking, old requirements can reappear and verified evidence can be drowned out by lower-authority text.

## Desired Outcome

- Retrieval ranking prefers frozen specs, verified artifacts, fresh verification claims, and recorded promotion receipts.
- Draft, stale, unavailable, superseded, or contradicted evidence is demoted or filtered according to explicit policy.
- ContextPack items explain why each result was selected: authority tier, freshness status, verification/promotion linkage, and demotion reasons.

## Acceptance Criteria

- [ ] SearchDocument projection exposes authority/freshness signals needed for ranking.
- [ ] Retrieval scoring applies stable boosts/demotions for authority tiers.
- [ ] ContextPack items include authority reason metadata.
- [ ] Stale/unavailable evidence cannot outrank fresh verified evidence for equivalent lexical matches.
- [ ] Existing lexical retrieval behavior remains deterministic.

## Constraints

- Do this after verify hardening, MCP surface repair, and agent authority boundary spec.
- Keep this slice lexical; do not add vector search.
- Do not treat retrieved evidence as authority over frozen current task docs.
