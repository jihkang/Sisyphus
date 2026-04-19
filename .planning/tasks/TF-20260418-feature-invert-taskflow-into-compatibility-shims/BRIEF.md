# Brief

## Task

- Task ID: `TF-20260418-feature-invert-taskflow-into-compatibility-shims`
- Type: `feature`
- Slug: `invert-taskflow-into-compatibility-shims`
- Branch: `feat/invert-taskflow-into-compatibility-shims`

## Problem

- After the core, MCP, and evolution migrations, the authoritative implementation mostly lives under `src/sisyphus`, but the package boundary still needs to make that ownership explicit for legacy entrypoints.
- In particular, `taskflow.cli` remained the practical implementation root for the console surface, and the compatibility contract needed to be tightened so `taskflow` resolves to canonical `sisyphus` modules consistently.
- This slice needs to make `sisyphus` the real implementation root for the remaining runtime surface while preserving `taskflow` as a supported legacy import and launcher namespace.

## Desired Outcome

- `sisyphus.cli` owns the CLI implementation.
- `taskflow.cli`, `taskflow.mcp_server`, and the legacy `taskflow` import surface resolve to canonical `sisyphus` implementations through compatibility aliasing.
- The legacy package remains supported without changing `.taskflow.toml` fallback behavior or persisted protocol identifiers.
- Compatibility tests explicitly prove that the legacy and canonical module paths point at the same runtime implementations.

## Acceptance Criteria

- [x] The CLI implementation is physically owned by `src/sisyphus/cli.py`.
- [x] `taskflow.cli` resolves to the same runtime module object as `sisyphus.cli`.
- [x] Legacy `taskflow` MCP and evolution module paths continue to resolve to canonical `sisyphus` implementations.
- [x] Focused regression coverage proves the compatibility alias contract across CLI, MCP, evolution, and adjacent runtime surfaces.
- [x] Compatibility-sensitive persisted identifiers remain intentionally unchanged.

## Constraints

- Do not break the legacy `taskflow` console entrypoint while shifting implementation ownership to `sisyphus`.
- Preserve `.taskflow.toml` fallback behavior and persisted protocol identifiers.
- Re-read the task docs before verify and close.
