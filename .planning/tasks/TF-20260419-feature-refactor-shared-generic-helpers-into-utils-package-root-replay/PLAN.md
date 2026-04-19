# Plan

## Implementation Plan

1. Align the replay task to the current root-adopted baseline so the helper refactor lands in the canonical `sisyphus` tree rather than an older task worktree snapshot.
2. Inspect the current live helpers and split them into two buckets.
   - generic helpers that can be reused safely across modules
   - domain-specific helpers that should stay near artifact, evolution, or MCP policy code
3. Convert `src/sisyphus/utils.py` into a `src/sisyphus/utils/` package while preserving current import ergonomics through `__init__.py` re-exports.
4. Add shared utility modules for the extracted generic helpers.
   - Introduce a coercion-oriented helper module for small data-normalization helpers such as optional string conversion and simple list coercion.
   - Keep mapping-oriented helpers such as `project_fields` and `find_unknown_fields` in a dedicated utility module instead of leaving everything in one flat file.
5. Update live callers to import the shared helpers from the new utils package and remove duplicated local implementations where the behavior is genuinely shared.
6. Add focused regression tests for the shared utils package behavior and the touched live modules such as `sisyphus.mcp_core` and `sisyphus.evolution.dataset`.
7. Update task docs and verification notes to record the final helper boundaries and test coverage.

## Risks

- Over-eager extraction can blur module boundaries by moving domain logic into a generic utils layer.
- Converting `utils.py` into a package can break existing imports if `__init__.py` does not preserve the current public surface.
- Small coercion helper changes can subtly alter MCP argument parsing or evolution dataset serialization if regression coverage is too narrow.

## Safety Invariants

- Only truly generic helper behavior moves into `src/sisyphus/utils/`.
- Artifact, projection, evolution policy, and promotion logic stay in their domain modules.
- The refactor must preserve current caller behavior and public import expectations.
- This slice does not change MCP tool/resource contracts or promotion/invalidation semantics.

## Test Strategy

### Normal Cases

- [ ] `sisyphus.utils` continues to expose the existing mapping helpers while also exposing the newly extracted generic coercion helpers.
- [ ] `sisyphus.mcp_core` and `sisyphus.evolution.dataset` still behave the same after switching to shared helper imports.

### Edge Cases

- [ ] `None` and empty-string values are normalized consistently by the shared coercion helper across multiple callers.
- [ ] List coercion still rejects non-list inputs with an actionable error where MCP argument parsing expects list data.

### Exception Cases

- [ ] Domain-specific helpers are not moved into the generic utils package during the refactor.

## Verification Mapping

- `sisyphus.utils continues to expose the existing mapping helpers while also exposing the newly extracted generic coercion helpers.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_utils`
- `sisyphus.mcp_core and sisyphus.evolution.dataset still behave the same after switching to shared helper imports.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_mcp_core tests.test_evolution`
- `None and empty-string values are normalized consistently by the shared coercion helper across multiple callers.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_utils`
- `List coercion still rejects non-list inputs with an actionable error where MCP argument parsing expects list data.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_utils tests.test_mcp_core`
- `Domain-specific helpers are not moved into the generic utils package during the refactor.` -> `manual review of touched modules`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
