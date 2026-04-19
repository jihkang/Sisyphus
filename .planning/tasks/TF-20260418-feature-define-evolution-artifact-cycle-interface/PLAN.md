# Plan

## Implementation Plan

1. Review the current evolution modules and existing artifact-centric architecture notes to determine which artifact kinds are needed for the next execution slices.
2. Define the minimum artifact kinds for the evolution vertical slice and the minimum fields each artifact must expose for reconstruction.
3. Distinguish artifact ownership between evolution-produced planning or evaluation artifacts and Sisyphus-authoritative execution or verification artifacts.
4. Update tests and docs so the artifact interface is explicit before orchestration or bridge work begins.

## Hard Risks

- If the artifact cycle is over-generalized, the project will start building a universal engine instead of the needed vertical slice.
- If the artifact cycle omits dependency or evidence fields, later promotion and invalidation work will not be reconstructable.
- If ownership is blurred, later tasks may treat evaluation artifacts as authoritative receipts.

## Safety Invariants

- This task must define a minimum evolution artifact cycle, not a repository-wide artifact substrate.
- Evolution artifacts and Sisyphus authoritative artifacts must remain distinguishable.
- The interface must support reconstruction without implying that all artifact kinds are already persisted at runtime.

## Out Of Scope

- Universal artifact registry or storage engine.
- Runtime orchestration behavior.
- CLI or MCP evolution surface.
- Promotion or invalidation implementation.

## Evidence Requirements

- Updated contract definitions in `src/sisyphus/evolution`.
- Updated architecture/evolution docs that map artifact kinds to owners and roles.
- Regression coverage that locks the artifact shape used by the next slices.

## Failure And Recovery

- If an artifact kind cannot be justified by the next execution slices, remove it from this task rather than carrying speculative types.
- If reconstructability fields are missing during review, revise the interface before plan approval rather than pushing ambiguity into later tasks.

## Test Strategy

### Normal Cases

- [ ] The minimum artifact kinds and fields support the current evolution slice without requiring a generic engine.

### Edge Cases

- [ ] Ownership boundaries remain clear between evolution-generated artifacts and Sisyphus authoritative artifacts.

### Exception Cases

- [ ] The interface does not overclaim runtime persistence for artifacts that are still future work.

## Verification Mapping

- `The minimum artifact kinds and fields support the current evolution slice without requiring a generic engine.` -> `targeted unit test in tests.test_evolution`
- `Ownership boundaries remain clear between evolution-generated artifacts and Sisyphus authoritative artifacts.` -> `manual review of docs and type definitions`
- `The interface does not overclaim runtime persistence for artifacts that are still future work.` -> `manual review of docs and type definitions`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
