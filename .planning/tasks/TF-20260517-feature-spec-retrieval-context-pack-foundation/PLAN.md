# Plan

## Implementation Plan

1. Inspect existing task record/document loading, artifact projection/snapshot resources, CLI dispatch, and MCP resource patterns.
2. Add a `SearchDocument` schema/projection module for task docs plus available feature artifact snapshots and verification claims.
3. Add a repo-local JSONL index module with deterministic rebuild/read behavior and clear handling for missing or malformed index files.
4. Add lexical retrieval over indexed documents using local token scoring, source metadata, excerpts, rank, score, and freshness/stale status.
5. Add a `ContextPack` schema/builder/persistence layer that selects top retrieval results, records provenance, limits text size, and fingerprints the pack deterministically.
6. Add CLI commands:
   - `sisyphus index rebuild`
   - `sisyphus search "<query>"`
   - `sisyphus context build "<query>"`
7. Add read-only MCP surfaces only if they are small and align with existing resource/tool patterns; provider prompt integration remains out of scope.
8. Add focused tests for projection, index rebuild/read, retrieval ranking, context pack creation, CLI output, and error handling.
9. Update verification notes after tests run.

## Out Of Scope

- Multi-turn memory as a separate authority layer.
- Provider prompt injection or workflow auto-injection of ContextPacks.
- Semantic/vector ranking or external search services.
- DAG validation/invalidation beyond surfacing existing snapshot freshness where available.
- Replacing artifact projection, artifact snapshot, conformance, or task lifecycle APIs.

## Risks

- SearchDocument projection can accidentally duplicate too much raw task text instead of producing bounded searchable records.
- Retrieval scores can become unstable if ordering, timestamps, or unordered collections leak into fingerprints.
- CLI/MCP additions can introduce compatibility churn if they do not follow existing parser and service conventions.
- ContextPack persistence can look authoritative unless it clearly records source refs, fingerprints, and freshness status.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `adds a new read-model/input-composition layer over existing task docs and artifact evidence while preserving lifecycle and provider execution boundaries`
- Confidence: `medium`
- Layer Impact: `layer-adding`
- Layer Decision Reason: `adds retrieval and context-pack modules plus CLI/MCP surfaces without changing task lifecycle authority`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Rebuilding the index projects task docs and artifact evidence into deterministic JSONL SearchDocuments.
- [ ] Searching a relevant query returns ranked results with source refs, excerpts, scores, and task metadata.
- [ ] Building a context pack persists a deterministic record with selected retrieval evidence and fingerprint.

### Edge Cases

- [ ] Tasks with missing optional docs or absent artifact snapshots still index available evidence.
- [ ] Empty or low-signal queries return an actionable empty-result response without crashing.
- [ ] Rebuilding without task changes produces stable document ids and fingerprints.

### Exception Cases

- [ ] Malformed index JSONL surfaces an actionable error.
- [ ] Context pack build handles a missing index by rebuilding or reporting the required action clearly.
- [ ] Non-feature tasks do not break artifact-evidence projection.

## Verification Mapping

- `SearchDocument projection and deterministic index rebuild` -> `targeted unit tests`
- `Lexical retrieval result ordering and metadata` -> `targeted unit tests`
- `ContextPack persistence and fingerprint stability` -> `targeted unit tests`
- `CLI commands for index/search/context` -> `targeted CLI tests`
- `Task lifecycle remains compatible` -> `sisyphus verify`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
