# Brief

## Task

- Task ID: `TF-20260517-feature-load-contextpack-into-workflow-input`
- Type: `feature`
- Slug: `load-contextpack-into-workflow-input`
- Branch: `feat/load-contextpack-into-workflow-input`

## Problem

- Sisyphus can now project task docs and artifact evidence into a repo-local search index and build ContextPack records, but worker execution still receives only the current task metadata and task docs.
- That means workflow/provider execution still depends on the current prompt and operator memory rather than a minimum evidence-grounded input composed from prior specs, artifact snapshots, and verification claims.
- The first production slice should connect ContextPack loading to provider prompt assembly without changing ranking strategy, workflow authority, or DAG validation.

## Desired Outcome

- Building a Codex worker prompt for a task also builds or loads a ContextPack from repo-local search evidence.
- The ContextPack excludes the current task's own docs so it is useful for prior context instead of echoing the task being executed.
- The prompt includes a compact, explicit ContextPack section with pack id, source refs, freshness, scores, matched terms, and excerpts.
- Missing search indexes are rebuilt automatically for prompt construction; malformed indexes fail loudly instead of silently omitting context.

## Acceptance Criteria

- [x] `build_codex_prompt` includes a ContextPack section when relevant prior evidence is found.
- [x] ContextPack construction for execution excludes documents from the current task id.
- [x] ContextPack prompt metadata is deterministic enough to inspect and reproduce: pack id, fingerprint, query, result count, source refs, freshness, scores, and document fingerprints are visible.
- [x] Missing search index files are rebuilt during prompt construction.
- [x] Malformed search indexes surface an actionable error to the caller.
- [x] Existing manual `sisyphus context build` behavior remains compatible.

## Constraints

- Keep this slice local and lexical; do not add vector ranking, semantic retrieval, provider-specific context APIs, or DAG validation.
- Do not let ContextPack become authority. Current frozen task docs remain the execution contract; ContextPack is supporting evidence.
- Avoid raw conversation history injection. Use only indexed task docs, artifact snapshots, and verification claims.
- Preserve existing provider wrapper behavior outside the added prompt context.
