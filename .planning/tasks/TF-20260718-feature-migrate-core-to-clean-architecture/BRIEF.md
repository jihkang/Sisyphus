# Brief

## Task

- Task ID: `TF-20260718-feature-migrate-core-to-clean-architecture`
- Type: `feature`
- Slug: `migrate-core-to-clean-architecture`
- Branch: `feat/migrate-core-to-clean-architecture`

## Problem

Sisyphus has responsibility-oriented package names, but its actual compile-time and runtime dependencies still form a transitional layered monolith. Domain services import concrete persistence, Git, provider, verification, metrics, and public facade modules. Core task/agent authority remains mutable dictionary state, transition rules are distributed, and at least one planning/lifecycle dependency cycle is hidden behind a local import.

This makes future changes to persistence, agent execution, verification, promotion, or typed models spread across large modules and transport surfaces. The problem is dependency ownership, not simply directory naming.

## Desired Outcome

- Domain policy is deterministic and independent of files, Git, subprocesses, MCP, CLI, and providers.
- Application use cases own orchestration and inward port contracts.
- Infrastructure implements persistence and external effects behind those ports.
- CLI, MCP, API, and compatibility surfaces delegate through one composition root.
- Existing public and persisted behavior remains compatible throughout an incremental migration.
- Architecture rules are executable and prevent new dependency drift.

## Acceptance Criteria

- [ ] `domain` has no imports from `infra`, `interfaces`, providers, compatibility facades, Git, filesystem persistence, subprocess execution, or transport modules.
- [ ] `application` has no imports from `infra`, `interfaces`, or stable root implementation facades.
- [ ] All concrete side effects used by core use cases are accessed through inward-owned ports and assembled in `bootstrap.py`.
- [ ] Task and agent persistence implementations live under `infra`, with centralized lossless mappers and no repetitive entity `to_dict()` implementations.
- [ ] Planning/lifecycle/workflow circular dependencies are removed rather than hidden with local imports.
- [ ] Existing task/agent JSON, document paths, event envelopes, receipts, CLI behavior, MCP schemas/resources, and public imports remain compatible.
- [ ] Existing locking, atomicity, stale-write, path-containment, and human-gate safety properties remain enforced.
- [ ] Architecture tests reject forbidden dependencies, cross-boundary cycles, and new business logic in compatibility facades.
- [ ] Evolution remains append-only/recommendation-oriented and cannot mutate approval, freeze, verification, activation, or promotion authority.
- [ ] Every migration slice has characterization, unit, contract, integration, and rollback evidence appropriate to its risk.
- [ ] Full tests, branch coverage, package build, installed-wheel smoke, Sisyphus verify, independent review, CI, PR merge, and merged-main revalidation pass.

## Constraints

- Use incremental strangler-style replacement; no big-bang rewrite.
- Start each mergeable slice from current `main` and preserve a green build after every slice.
- Keep stable public facades until repository-wide and installed-wheel compatibility checks prove removal is safe.
- Do not require an in-place persisted-state migration.
- Add no runtime framework solely for dependency injection, mapping, or validation.
- Do not weaken repository-local authority, conformance gates, path security, or promotion judgment boundaries.
- Shared architecture documentation describes only merged and verified implementation, not speculative target state.

## Non-Goals

- Microservice or container decomposition
- Database or event-sourcing migration
- Public task/MCP/CLI schema redesign
- Package rename or release-policy work
- Hermes/GEPA and 30.5B model benchmarking from the separate Harness roadmap
