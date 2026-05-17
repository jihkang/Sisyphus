# Brief

## Task

- Task ID: `TF-20260517-feature-spec-retrieval-context-pack-foundation`
- Type: `feature`
- Slug: `spec-retrieval-context-pack-foundation`
- Branch: `feat/spec-retrieval-context-pack-foundation`

## Problem

- Sisyphus currently stores task specs, docs, artifact projections, snapshots, verification claims, and conformance state, but there is no first-class way to search those records and compose only the relevant evidence for a new action.
- The problem is not multi-turn memory, agent memory, provider orchestration, or a DAG-first lineage store. Authoritative memory should remain frozen/versioned specs plus artifact and verification evidence.
- The first slice should add a repo-local retrieval/input-composition foundation that can project existing task docs and artifact evidence into searchable documents, rebuild a JSONL index, rank matching records lexically, and persist a minimal evidence-grounded ContextPack.

## Desired Outcome

- Operators can run `sisyphus index rebuild`, `sisyphus search "<query>"`, and `sisyphus context build "<query>"` against the repository-local task/evidence store.
- Search results identify source task/docs/artifact evidence, scores, excerpts, provenance, and freshness/stale status where known.
- ContextPack output gives the next planner/executor a deterministic, minimal input bundle without relying on raw conversation history.
- Provider prompt integration, workflow auto-injection, semantic/vector ranking, and DAG validation/invalidation remain follow-up work.

## Acceptance Criteria

- [ ] `SearchDocument` projection covers task `BRIEF`, `PLAN` or `FIX_PLAN`, `VERIFY`, `LOG`, and available feature artifact snapshots / verification claims.
- [ ] A repo-local JSONL search index can be rebuilt deterministically and read back without external services.
- [ ] Lexical retrieval returns ranked matches with source references, scores, excerpts, task metadata, and freshness/stale status when available.
- [ ] `ContextPack` records can be built and persisted with query text, selected source refs, ranked evidence items, deterministic fingerprints, and limits for result count/text size.
- [ ] CLI commands exist for `sisyphus index rebuild`, `sisyphus search "<query>"`, and `sisyphus context build "<query>"`.
- [ ] Focused tests cover projection, index rebuild/read, lexical ranking, context pack construction, CLI behavior, and malformed/missing index handling.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not replace existing artifact projection or snapshot APIs; use them as sources.
- Do not add provider prompt injection, workflow auto-injection, vector search, external search services, or a new DAG validation layer in this slice.
