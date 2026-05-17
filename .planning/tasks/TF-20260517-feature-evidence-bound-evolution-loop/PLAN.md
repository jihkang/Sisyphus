# Plan

## Implementation Plan

1. Treat verify hardening, MCP runtime repair, agent authority boundaries, and authority-aware search as prerequisites.
2. Inventory existing evolution registry, dataset, harness, constraints, promotion gate, and operator surfaces.
3. Define a closed-loop stage contract:
   - dataset/context build,
   - candidate proposal,
   - isolated materialization,
   - evaluation,
   - evidence projection,
   - review gate decision,
   - promotion or invalidation.
4. Enforce no self-approval: proposer, evaluator, reviewer, and promoter decisions must be separate records.
5. Add tests for successful evidence-bound loop and failed candidate invalidation.
6. Expose only bounded operator/MCP commands after local tests pass.

## Risks

- Evolution can amplify weak verification if started before prerequisites are complete.
- Candidate generation can mutate the live repo if isolation is incomplete.
- Review gates can become ceremonial unless authority/evidence refs are enforced.

## Design Evaluation

- Design Mode: `full`
- Decision Reason: `adds a closed automation loop across dataset, candidate execution, review, verification, and promotion`
- Confidence: `medium`
- Layer Impact: `layer-reshaping`
- Layer Decision Reason: `reshapes evolution from read-only planning into evidence-bound execution orchestration`
- Required Design Artifacts: `stage contract, authority matrix, sequence diagram`

## Design Artifacts

- Connection Diagram: `pending`
- Sequence Diagram: `pending`
- Boundary Note: `pending`

## Test Strategy

### Normal Cases

- [ ] Bounded candidate completes isolated evaluation and records evidence.
- [ ] Review gate approval plus verified evidence makes promotion eligible.

### Edge Cases

- [ ] Candidate with partial metrics remains pending, not fabricated.
- [ ] Search/ContextPack inputs are supporting evidence, not promotion authority.
- [ ] Multiple candidates do not overwrite each other's evidence.

### Exception Cases

- [ ] Failed evaluation records invalidation evidence.
- [ ] Missing review gate blocks promotion.
- [ ] Live repo mutation attempt fails closed.

## Verification Mapping

- `Evidence-bound happy path` -> `python -m unittest tests.test_evolution -v`
- `Invalidation path` -> `python -m unittest tests.test_evolution -v`
- `No live repo mutation` -> `python -m unittest tests.test_evolution.EvolutionHarnessTests -v`
- `Operator/MCP surface` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core -v`

## External LLM Review

- Required: `yes`
- Provider: `tbd`
- Purpose: `review closed-loop safety, authority separation, and promotion constraints`
- Trigger: `before implementation approval`
