# ADR 0001: Clean Architecture Boundaries

- Status: Accepted
- Date: 2026-07-20
- Task: `TF-20260718-feature-migrate-core-to-clean-architecture`

## Context

Sisyphus began as a flat package in which public modules combined lifecycle
policy, orchestration, filesystem access, subprocess execution, persistence, and
wire mapping. That structure preserved a convenient import surface but made
authority difficult to locate and caused a change in one concern to affect
unrelated entry points.

The migration must improve dependency direction without changing supported
Python imports, CLI/MCP behavior, persisted record compatibility, or lifecycle
gates. Repository artifacts remain authoritative; an agent session or Evolution
run does not become a second source of task truth.

## Decision

### 1. Dependency direction

The dependency rule is:

```text
interfaces/public facades -> composition -> application -> domain
                                      |
                                      +-> infrastructure adapters

infrastructure -> application ports + domain + shared
```

- `domain` contains deterministic entities, value objects, and policy.
- `application` contains commands, results, ports, use-case ordering, pure
  projections, and boundary codecs.
- `composition` is the only normal construction boundary that selects concrete
  adapters.
- `infra` contains repository, clock, Git, process, provider, event, and other
  external effects.
- `interfaces` parse and render transport data and invoke composed use cases.
- `shared` is limited to dependency-light primitives.

Application and domain code may not import concrete infrastructure. Interfaces
may not bypass composition to select infrastructure directly.

### 2. Model, mapper, and codec ownership

Canonical domain and application model definitions do not declare `to_dict`,
`from_dict`, `to_json`, or `from_json`. Serialization is a boundary responsibility:

- task and agent persistence mappings live in `infra/persistence`
- extension-preserving dataclass mapping lives in `record_mapper.py`
- application-owned wire contracts use explicit `application/codecs`
- provider/evaluation boundary shapes use codecs in their bounded context
- untrusted inbox input is parsed strictly in `interfaces/inbox`

This prevents models from becoming an implicit persistence schema while retaining
unknown legacy fields and omitted-field behavior where compatibility requires it.
Published classes that exposed mapping methods before this migration regain them
only when imported through a stable outer facade. The centralized
`compat.serialization` helper installs delegating methods backed by the canonical
codecs, preserving the public API without duplicating schema logic in each model.

### 3. Compatibility facades and shims

Stable public modules remain thin delegates or compatibility-only facades so
existing imports and supported monkeypatch points retain their behavior. A facade
may additionally install codec-delegating legacy serialization methods, but may
not become a second implementation root.

Exactly two domain outward imports are temporarily accepted:

| Compatibility path | Canonical implementation |
| --- | --- |
| `domain/agent/repository.py` | `infra/persistence/agent_repository.py` |
| `domain/task/repository.py` | `infra/persistence/task_repository.py` |

Each shim may contain only a docstring, explicit imports, and literal `__all__`.
No third exception is permitted. A shim can be removed only after repository-wide
import inspection and an installed-wheel compatibility window show that the old
path is no longer a supported consumer dependency. The architecture allowlist
must shrink in the same change that removes it.

### 4. Lifecycle and Evolution authority

The canonical task record and frozen task documents own lifecycle authority.
Plan approval, spec freeze, final verification, close, policy activation,
promotion execution, and merged-PR recording remain control-side judgment gates.

Evolution may:

- read bounded task, artifact, event, and verification projections
- construct datasets and evaluation plans
- execute isolated candidate evaluation through infrastructure adapters
- score candidates and persist append-only reports
- request a normal follow-up task

Evolution may not approve a plan, freeze a spec, verify or close a task, activate
a policy, or promote repository state. Follow-up work re-enters the normal
Sisyphus request and lifecycle path with `auto_run=False`.

### 5. Effect ordering

Application use cases own transaction order and recovery decisions. Ports expose
narrow effects; adapters implement those effects without deciding lifecycle
policy. Durable writes use the repository's locking, containment, no-follow,
atomic replacement, and fsync primitives appropriate to each store.

## Consequences

Positive consequences:

- business policy can be tested without filesystem, Git, network, or subprocesses
- effect ownership and lifecycle authority have one discoverable location
- serialization changes are explicit and independently testable
- outer adapters can be replaced without moving policy
- legacy consumers continue to import supported symbols during migration

Costs and constraints:

- composition modules contain deliberate wiring code
- commands, results, ports, and codecs add small explicit types
- the two repository compatibility shims remain tracked debt
- public patch-point compatibility constrains some facade decomposition
- cross-boundary changes require parity tests at both service and public surfaces

## Enforcement

`tests/test_architecture_dependencies.py` enforces dependency direction, cycle
freedom, facade restrictions, model serialization ownership, hotspot extraction,
and the exact two-shim allowlist. Persistence, interface, mapping, workflow,
verification, artifact, Evolution, and promotion tests enforce behavioral parity.
`tests/test_repository_hygiene.py` checks that these documents name existing
canonical modules and do not restore superseded ownership claims.

See [the architecture overview](../architecture.md),
[the data pipeline](../architecture-and-data-pipeline.md), and
[the implementation debt ledger](../clean-architecture-implementation-debt.md).
