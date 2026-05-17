# Plan

## Implementation Plan

1. Add ContextPack filtering support so callers can exclude the current task from retrieval results.
2. Add task execution ContextPack helpers that derive a query from current task docs and metadata, build or rebuild the search index as needed, persist the pack, and record purpose/source-task metadata.
3. Extend Codex prompt assembly to include a bounded ContextPack section after task metadata and before task docs.
4. Keep provider and workflow call sites stable by routing through the existing `build_codex_prompt` path rather than adding a new execution layer.
5. Add focused tests for prompt inclusion, current-task exclusion, missing-index rebuild, malformed-index failure, and existing context CLI compatibility.

## Risks

- ContextPack prompt text could become too large or drown out the frozen task docs if excerpts are not bounded.
- If current-task docs are not excluded, retrieval will mostly echo the task prompt and fail to provide useful prior evidence.
- Rebuilding the index during prompt construction adds filesystem side effects that must stay deterministic and inspectable.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `connects retrieval/context-pack read model to provider prompt assembly while preserving lifecycle authority`
- Confidence: `medium`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `touches the provider input boundary but does not add a new execution engine`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [x] Codex prompt includes a ContextPack section sourced from prior task evidence.
- [x] Execution ContextPack persists with source task id, purpose, fingerprint, and selected evidence items.
- [x] Existing CLI context build still persists a compatible ContextPack.

### Edge Cases

- [x] The current task's own docs are excluded from execution ContextPack retrieval.
- [x] Missing search index is rebuilt automatically during prompt construction.
- [x] No matching prior evidence produces a clear empty ContextPack section without blocking prompt creation.

### Exception Cases

- [x] Malformed search index fails prompt construction with an actionable search index error.
- [x] Invalid persisted ContextPack schema still fails loudly when read through existing APIs.

## Verification Mapping

- `Codex prompt includes a ContextPack section sourced from prior task evidence` -> `python -m unittest tests.test_search_context.SearchContextTests -v`
- `Execution ContextPack persists with source task id, purpose, fingerprint, and selected evidence items` -> `python -m unittest tests.test_search_context.SearchContextTests -v`
- `Existing CLI context build still persists a compatible ContextPack` -> `python -m unittest tests.test_search_context.SearchContextTests -v`
- `Current task's own docs are excluded` -> `python -m unittest tests.test_search_context.SearchContextTests -v`
- `Missing search index is rebuilt automatically` -> `python -m unittest tests.test_search_context.SearchContextTests -v`
- `Malformed search index fails prompt construction` -> `python -m unittest tests.test_search_context.SearchContextTests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
