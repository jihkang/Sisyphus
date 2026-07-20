# Sisyphus Architecture

Last verified against code: 2026-07-20

Sisyphus is a repository-local control plane for AI-assisted software work. It
turns requests into reviewable task state, isolated Git worktrees, bounded agent
execution, verification evidence, and promotion receipts. Repository artifacts,
not an agent session, are authoritative.

This document is the architecture overview. See
[architecture-and-data-pipeline.md](./architecture-and-data-pipeline.md) for the
module-level data flow and [runtime-relationship-diagrams.md](./runtime-relationship-diagrams.md)
for focused diagrams.

## Architectural Rules

The implemented dependency direction is:

```text
interfaces and public facades
            |
            v
       composition
            |
            v
       application
            |
            v
          domain

composition ------> infrastructure adapters
infrastructure ---> application ports + domain + shared
```

- `domain` owns deterministic business values and policies. It does not own IO,
  transport, clocks, subprocesses, or boundary serialization.
- `application` owns commands, results, ports, use-case ordering, projections,
  and explicit boundary codecs.
- `composition` is the wiring boundary. It is where concrete infrastructure is
  selected for application ports.
- `infra` owns repository files, locking, atomic replacement, Git, subprocesses,
  provider receipts, event storage, and other external effects.
- `interfaces` own CLI, MCP, inbox, and provider-wrapper parsing, dispatch, and
  presentation. Interfaces do not import infrastructure directly.
- `shared` contains dependency-light primitives, not business services.
- stable root modules and `compat` preserve supported imports and patch points;
  they must not become a second implementation root.

These rules are executable. `tests/test_architecture_dependencies.py` rejects
outward application imports, direct interface-to-infrastructure imports, cycles,
business logic returning to facades, model-owned mapping methods, and any domain
outward edge beyond the two named compatibility shims.

## Package Ownership

| Package | Owns | Representative modules |
| --- | --- | --- |
| `domain` | entities, value objects, lifecycle and promotion policy, artifact semantics | `domain/lifecycle`, `domain/task`, `domain/artifact`, `domain/promotion` |
| `application` | commands, ports, use cases, result types, pure projections and codecs | `application/use_cases`, `application/ports`, `application/codecs` |
| `composition` | construction of application services with concrete adapters | `composition/workflow.py`, `composition/verification.py`, `composition/promotion.py` |
| `infra` | file, process, Git, provider, event, search, verification, and persistence adapters | `infra/persistence`, `infra/workspace`, `infra/verification`, `infra/evolution` |
| `interfaces` | CLI/MCP/inbox/provider transport adaptation | `interfaces/cli`, `interfaces/mcp`, `interfaces/inbox` |
| `evolution` | effect-free evolution plans, datasets, scoring, reports, and request contracts | `evolution/harness.py`, `evolution/fitness.py`, `evolution/report.py` |
| `providers` | legacy-facing and local-model adapter surface | `providers/local_agent.py`, `providers/benchmark.py` |
| `shared` | time, paths, coercion, serialization primitives | `shared/clock.py`, `shared/paths.py`, `shared/serialization.py` |

`providers` and `evolution` are bounded outer contexts, not additions to the
domain core. Their effects are routed through infrastructure and composition.

## Authority Model

### Canonical task authority

The canonical task record is:

```text
.planning/tasks/<task-id>/task.json
```

It owns lifecycle, planning, verification, conformance, subtask, and repository
promotion state. Task documents and artifacts are referenced from this record.
The record is accessed through application repository ports backed by
`infra/persistence/task_records.py` and `task_repository.py`.

### Durable supporting authority

Important task-local artifacts include:

```text
BRIEF.md
PLAN.md or FIX_PLAN.md
REPRO.md                    # issue tasks
VERIFY.md
LOG.md
agents/*.json
artifacts/spec-validation/latest.json
artifacts/evidence/evidence-graph.json
artifacts/projection/feature-change.json
artifacts/obligations/compiled.json
artifacts/promotion/*.json
```

Derived indexes such as `.planning/cache/workflow-candidates.json` and search
JSONL files are rebuildable. They never override `task.json`.

### Human authority

Plan approval, spec freeze, close, promotion execution, and merged-PR recording
remain judgment-gated actions. The compact resource
`task://<task-id>/observation` projects allowed and forbidden next actions from
canonical state; clients must not reconstruct lifecycle authority from chat.

### Evolution authority

Evolution can read task/evidence data, construct datasets, compare candidates,
score fitness, persist append-only run artifacts, and request a normal follow-up
task. It cannot approve, freeze, verify, activate, close, or promote canonical
task state. Those effects are assembled by control-owned composition and pass
through normal Sisyphus lifecycle gates.

## Domain And Application Boundaries

The domain layer is intentionally small and deterministic:

- lifecycle snapshots and transition policy
- task, planning, agent, verification, promotion, and artifact values
- promotion defaults and base state
- artifact DSL and evaluation values
- workspace mutation/completion policy

Application services coordinate these rules over ports. Major use cases include:

- inbox queue and processing
- task record and workspace creation
- plan review, spec validation, and spec freeze
- workflow advancement and subtask execution
- obligation convergence
- verification and evidence recording
- head-bound external LLM review evidence recording
- closeout
- repository promotion execution and merged-PR recording
- search, observation, lifecycle, artifact, and repository queries

Application services decide effect order. Adapters do not decide lifecycle
policy.

## Composition Boundary

The `composition` package is the only normal construction point that knows both
application abstractions and concrete infrastructure. For example:

- `composition/workflow.py` wires `WorkflowService` to task, planning,
  obligation, provider, verification, closeout, event, and intervention adapters.
- `composition/verification.py` wires command execution, documents, spec
  validation, conformance, evidence, events, and clock.
- `composition/external_review.py` wires task persistence to bounded review
  report inspection, Git HEAD binding, digesting, and time.
- `composition/promotion.py` wires Git, GitHub CLI, task records, artifacts,
  closeout, interventions, and time.
- `composition/repository_requests.py` wires inbox queue/processing to workflow
  advancement and task queries.

Composition functions may provide stable convenience entry points. They should
not contain business policy that belongs in an application service.

## Persistence And Mapping

Canonical domain and application model definitions do not declare `to_dict`,
`from_dict`, `to_json`, or `from_json`. Boundary shapes have explicit owners:

- task and agent persisted records: `infra/persistence/*_mapper.py`
- generic extension-preserving dataclass mapping:
  `infra/persistence/record_mapper.py`
- artifact, event, episode, search, snapshot, and execution-policy shapes:
  `application/codecs/`
- local provider and benchmark result shapes: `providers/codecs.py`
- evaluation wire shapes: `eval/codecs.py` and `benchmark_codec.py`
- strict inbound inbox shapes: `interfaces/inbox/parser.py` and `mapper.py`

For previously published model classes, stable outer facades restore the legacy
methods with `compat.serialization.install_serialization_compat`. Those methods
delegate directly to the codecs above; they do not define a second wire shape or
move serialization policy back into the canonical model source.

`DataclassRecordMapper` retains unknown fields, omitted mapped fields, and input
field order through a `RecordEnvelope`. This preserves legacy task/agent records
without making domain entities a second schema authority.

## Effects And Safety

Concrete effects are isolated in infrastructure:

- locked atomic JSON replacement with file and directory fsync
- bounded, descriptor-relative support-file mirroring into task worktrees
- descriptor-relative no-follow workspace reads and writes
- path containment and symlink rejection
- bounded subprocess output, process-group timeout, and strict command parsing
- Git patch tree hashing and postcondition checks
- provider request/receipt digest verification
- append-only, bounded evolution run storage
- durable JSONL event appends

The verifier executes through `VerificationCommandPort`; verification policy and
gate ordering remain in `VerificationService`. Workspace mutation policy is
domain-owned, while Git and test subprocesses are infrastructure adapters.

## Public Compatibility

Stable top-level modules remain for Python consumers and tests. Most are
import-only facades or thin delegates; facades for formerly model-owned
serialization may additionally install codec-delegating legacy methods through
the single compatibility helper. Two outward imports remain inside domain only
for import compatibility:

| Legacy import | Canonical implementation |
| --- | --- |
| `sisyphus.domain.agent.repository` | `sisyphus.infra.persistence.agent_repository` |
| `sisyphus.domain.task.repository` | `sisyphus.infra.persistence.task_repository` |

They contain no behavior. Their exact allowlist and retirement conditions are in
[clean-architecture-implementation-debt.md](./clean-architecture-implementation-debt.md).

## Conformance Semantics

Conformance colors are canonical and shared across task, workflow, and evolution
projections:

- `green`: aligned with the frozen spec; execution may continue if other gates pass
- `yellow`: unresolved warning or clarification; final verify and close are blocked
- `red`: blocking drift; execution must stop until reconciled

The color is a policy result, not a UI decoration.

## Architecture Decisions

The migration decision, mapper ownership, compatibility lifetime, and Evolution
authority are recorded in
[ADR 0001](./adr/0001-clean-architecture-boundaries.md).

The remaining implementation and release work is tracked in
[clean-architecture-implementation-debt.md](./clean-architecture-implementation-debt.md).
The migration review is recorded in
[clean-architecture-final-review-2026-07-20.md](./reviews/clean-architecture-final-review-2026-07-20.md).

## Scope Boundary

This repository contains the Sisyphus control plane and a bounded local-agent
adapter. The separate Sisyphus Harness roadmap for Docker service separation,
Hermes agent evolution, GEPA, and real 30.5B model benchmark evidence is not part
of this core architecture migration.
