# Authority Boundary

## Ownership

### Domain

Owns task and agent identity, lifecycle states, transition policy, gate decisions, promotion eligibility, and other deterministic invariants. Domain code cannot know repository paths, JSON, Git, providers, subprocesses, MCP, CLI, or concrete clocks.

### Application

Owns commands, queries, orchestration order, transaction boundaries, retry decisions, and the ports required to perform effects. It decides when an effect is requested but does not implement the effect.

### Infrastructure

Owns file persistence, locking, atomic replacement, task-document IO, Git/worktrees, providers, verifier subprocesses, GitHub access, JSONL events, artifact storage, and system time. It implements application-owned ports and cannot redefine lifecycle policy.

### Interfaces

Own transport parsing, authentication/config entry, command dispatch, tracing adaptation, response presentation, and exit/status mapping. Interfaces cannot directly mutate canonical task, approval, verification, or promotion state.

### Composition Root

`bootstrap.py` owns concrete selection and wiring. It is the deliberate exception that imports both inward contracts and outward adapters. Business decisions are not allowed in this module.

### Evolution

Evolution owns dataset projection, candidate planning/comparison, bounded evaluation, append-only run artifacts, fitness, and recommendations. It may request a normal review-gated follow-up task. It cannot approve plans, freeze specs, mark verification passed, activate policy, execute promotion, record a merge without operator evidence, or mutate canonical task authority directly.

## Data Authority

- Existing repository-local `task.json`, agent records, task documents, and artifact schemas remain the persistence contract for this migration.
- Domain objects are in-memory authority for a single use-case decision, not an alternate persistence schema.
- One mapper per persisted aggregate translates storage records and preserves unknown fields.
- Interface presenters own transport projections; persistence mappers are never reused as MCP/CLI serializers.
- Stable facades expose compatibility, not a second implementation root.

## Review And Promotion Authority

Plan approval, spec freeze, promotion execution, and merged-PR recording remain operator/review-gated actions. Dependency injection must not make these actions callable through lower-risk code paths. Architecture tests and lifecycle tests must verify that transport availability does not imply authority.

## Compatibility Lifetime

A compatibility facade is removed only when all repository imports, installed-wheel public imports, CLI/MCP contract tests, and downstream wrapper tests pass without it. Until then, the facade delegates to the application facade and contains no persistence, policy, provider selection, or effect execution.
