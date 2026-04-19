# Plan

## Implementation Plan

1. Update the architecture documentation so Sisyphus is defined as an artifact-centric, graph-native work system rather than only a task orchestration stack.
2. Capture the hard-state versus soft-cognition boundary, reconstructability requirement, composite artifact model, and promotion or invalidation rules in repository docs.
3. Record the best concrete next design step as a representative composite-artifact protocol definition, and align the task docs with that result.

## Risks

- The repository already has implementation-oriented architecture docs, so the new conceptual model must extend them without contradicting the current runtime layout.
- The design summary spans several abstractions at once, so the document must distinguish current implementation from target model clearly enough to avoid overclaiming what is already built.

## Test Strategy

### Normal Cases

- [x] Architecture docs describe Sisyphus as an artifact-centric work system with a clear authority boundary.

### Edge Cases

- [x] The document explains how task-centric runtime pieces still fit into an artifact-centric target model.

### Exception Cases

- [x] The document records one concrete next design lock instead of leaving the direction at philosophy-only level.

## Verification Mapping

- `Architecture docs describe Sisyphus as an artifact-centric work system with a clear authority boundary.` -> `manual review of docs/architecture.md and docs/self-evolution-mcp-plan.md`
- `The document explains how task-centric runtime pieces still fit into an artifact-centric target model.` -> `manual review of conceptual sections versus current system-shape sections`
- `The document records one concrete next design lock instead of leaving the direction at philosophy-only level.` -> `manual review of the next-design-lock section`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
