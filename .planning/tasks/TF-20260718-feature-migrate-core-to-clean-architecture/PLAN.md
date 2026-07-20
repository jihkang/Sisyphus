# Plan

## Objective

Incrementally reshape Sisyphus into a Clean Architecture-aligned modular monolith without changing its public Python API, CLI grammar, MCP contracts, repository-local task format, artifact layout, lifecycle policy, or observable side-effect ordering.

The migration must remain releasable after every slice. Existing facades stay in place until all callers have moved to inward-owned application contracts and parity tests prove that the replacement path is equivalent.

## Current Baseline

The baseline review identified these structural facts on current `main`:

- `domain` directly imports concrete persistence in four modules and imports top-level implementation modules in dozens of places.
- `domain/task/repository.py` combines persistence, schema defaults, projection normalization, document parsing, worktree mirroring, and optimistic concurrency tracking.
- `domain/workflow/service.py` directly coordinates persistence, provider execution, verification, closeout, events, metrics, conformance, and obligation convergence.
- `domain/promotion/service.py` combines promotion policy with Git, GitHub CLI, subprocess, receipt persistence, and task mutation.
- task and agent authority is represented primarily by mutable dictionaries, while transition invariants are distributed across planning, lifecycle, workflow, audit, closeout, and promotion modules.
- the planning/lifecycle path contains a real dependency cycle currently avoided with a function-local import.
- the repository already has useful adapter patterns in `EventPublisher`, `ChatCompletionClient`, CLI handlers, MCP registries, atomic JSON persistence, and injectable evolution evaluators. These are migration anchors, not code to replace gratuitously.

Before implementation, Phase 0 must recalculate and persist the exact import graph, cycle list, module-size inventory, test count, branch coverage, public exports, CLI command list, MCP tool/resource schemas, and representative task JSON fixtures from the task branch baseline.

## Architectural Invariants

1. `domain` imports only the standard library, dependency-light `shared` primitives, and other domain modules.
2. `application` imports domain types and application-owned ports/DTOs, never `infra`, `interfaces`, compatibility facades, MCP, CLI, Git, filesystem, subprocess, or provider implementations.
3. Port protocols are owned by `application`; concrete adapters are owned by `infra`.
4. `interfaces` parse transport input and present application results. They do not load or mutate task records directly.
5. `bootstrap.py` is the only normal composition root allowed to import both application use cases and concrete infrastructure adapters.
6. `compat` and stable top-level modules delegate only. They do not regain business rules, persistence, or provider selection.
7. Existing task JSON keys, unknown extension fields, task document paths, event envelopes, artifact paths, CLI exit codes, MCP response shapes, and public imports remain compatible unless a separately approved schema change is created.
8. Domain models do not implement repetitive `to_dict()` methods. Persistence and transport serialization use explicit, centrally tested mappers at adapter boundaries.
9. No persisted-state rewrite is required for deployment. Readers accept the existing format and writers continue producing the existing canonical format throughout this task.
10. Human-only lifecycle gates, evolution authority limits, repository path containment, and atomic-write guarantees may not be weakened by the refactor.

## Target Package Shape

```text
src/sisyphus/
  domain/
    task/
      entities.py
      value_objects.py
      policies.py
    agent/
      entities.py
      policies.py
    lifecycle/
      actions.py
      decisions.py
      policies.py
    planning/
      policies.py
    promotion/
      policies.py
  application/
    commands/
    results/
    ports/
      task_repository.py
      agent_repository.py
      task_documents.py
      workspace.py
      provider.py
      verification.py
      version_control.py
      pull_requests.py
      artifacts.py
      events.py
      clock.py
    use_cases/
      task.py
      planning.py
      workflow.py
      verification.py
      promotion.py
  infra/
    persistence/
      task_repository.py
      agent_repository.py
      task_record_mapper.py
      agent_record_mapper.py
      task_documents.py
    workspace/
      git.py
    providers/
    verification/
    promotion/
      git.py
      github.py
    events/
    clock.py
  interfaces/
    cli/
    mcp/
  evolution/
  shared/
  compat/
  bootstrap.py
```

The exact file count may change during implementation, but ownership and import direction may not. `evolution` remains a bounded control-plane context; it consumes application contracts and append-only artifact ports without gaining lifecycle, approval, verification, or promotion authority.

## Port Boundaries

| Port | Inward owner | Concrete implementation | Contract requirement |
| --- | --- | --- | --- |
| `TaskRepository` | application | atomic file repository | load/list/create/compare-and-update without exposing storage paths to use cases |
| `AgentRepository` | application | atomic file repository | preserve stale-write detection and existing record shape |
| `TaskDocumentPort` | application | repository-local Markdown store | read/write/mirror documents with containment checks |
| `WorkspacePort` | application | Git worktree adapter | create, inspect, adopt, and remove workspaces with current rollback behavior |
| `ProviderPort` | application | Codex, Claude, local OpenAI adapters | execute tracked work without importing CLI handlers |
| `VerificationPort` | application | bounded subprocess verifier | preserve command order, timeout, output, and receipt semantics |
| `VersionControlPort` | application | Git adapter | stage, commit, push, branch, and remote operations |
| `PullRequestPort` | application | GitHub CLI adapter | open/read PR state without leaking subprocess details |
| `ArtifactStorePort` | application | repository-local artifact store | atomic append/write/read with stable paths and schemas |
| `EventPublisherPort` | application | noop and JSONL adapters | publish normalized envelopes; failures follow existing policy |
| `ClockPort` | application | UTC system clock | deterministic timestamps in unit tests |

A port is introduced only for an actual side effect, nondeterministic dependency, or independently replaceable boundary. Pure helpers and one-line transformations remain ordinary functions.

## Model And Mapping Strategy

- Introduce typed identifiers, status enums, immutable decision/result objects, and a task aggregate or task snapshot that owns lifecycle invariants.
- Keep persistence models separate from domain models. Existing JSON records are decoded by `TaskRecordMapper` and `AgentRecordMapper` and encoded back into the same shape.
- Preserve unknown top-level and nested extension fields so older/newer task records round-trip without data loss.
- Transition policies return typed decisions or patches rather than mutating arbitrary dictionaries across modules.
- Transport DTOs remain interface-specific. MCP and CLI presenters convert application results without adding serialization methods to domain entities.
- Characterization tests compare normalized bytes or exact dictionaries where the current contract is byte-sensitive.

## Implementation Plan

### Phase 0 - Freeze The Behavioral Baseline

1. Start from updated `main` in the dedicated task worktree and confirm no unrelated tracked changes.
2. Record the internal import matrix, strongly connected components, public symbol inventory, CLI command paths, MCP definitions, and module-size inventory under task-local evidence.
3. Run the full test suite, branch coverage, package build, installed-wheel smoke test, and security-focused path/inbox tests.
4. Add characterization fixtures for representative feature and issue tasks, agent records, plan/spec transitions, verify results, promotion receipts, event envelopes, CLI output, and MCP payloads before changing their implementation.
5. Record nondeterministic fields that must be normalized in parity comparisons, such as timestamps, temporary paths, PIDs, and generated IDs.

Exit gate: baseline evidence is reproducible, all existing tests pass, and every behavior that later phases may move has at least one characterization test.

Rollback: no runtime code changes occur in this phase.

### Phase 1 - Add Architecture Guardrails And Package Skeleton

1. Add `application/commands`, `application/results`, `application/ports`, and `application/use_cases` packages without routing production behavior through them yet.
2. Add an AST-based architecture test that expresses the target dependency rules.
3. Seed a reviewed baseline allowlist for existing violations. The test fails on every new violation and reports the owner and removal phase for each allowed edge.
4. Add cycle detection for cross-boundary module imports and a facade rule that prohibits business logic in `compat` and stable root shims.
5. Document the composition-root rule and the bounded-context exception for `evolution`.

Exit gate: no observable behavior changes; architecture tests pass and prevent the violation count from increasing.

Rollback: remove only the new guard and empty packages.

### Phase 2 - Establish The Typed Domain Kernel

1. Introduce typed task and agent identifiers, lifecycle actions, statuses, gate decisions, and transition results using standard-library dataclasses and enums.
2. Move pure transition policy from `lifecycle_rules.py` and planning status checks into inward domain policies.
3. Introduce task/agent record mappers that can round-trip every baseline fixture, including unknown fields.
4. Wrap existing dictionary callers behind compatibility conversion functions while keeping public return shapes unchanged.
5. Add property-style table tests for every lifecycle action across open, blocked, verified, promotion-pending, and closed states.
6. Prohibit direct JSON/path/subprocess imports from the new domain kernel.

Exit gate: typed policies produce the same allowed actions, gates, phases, and statuses as baseline fixtures; mapper round trips are lossless.

Rollback: callers remain on legacy dictionaries; the new kernel is additive until parity is proven.

### Phase 3 - Introduce Application Ports And Composition Root

1. Define the ports listed above with narrow method contracts and typed commands/results.
2. Build legacy-backed adapters that call the current functions, allowing application use cases to be exercised before implementations move.
3. Add `bootstrap.py` to assemble configuration, repositories, provider, verifier, workspace, event, clock, and promotion adapters for a repository root.
4. Add in-memory fakes for application tests; fakes must satisfy the same contract suite as concrete adapters.
5. Route one read-only use case, such as task observation/listing, through the application facade and compare old/new projections in tests.

Exit gate: the composition root is the only new module importing both ports and concrete adapters; read-only parity is exact.

Rollback: switch the selected interface call back to its stable facade; no persisted data changes.

### Phase 4 - Move Task, Agent, And Document Persistence Outward

1. Move concrete task and agent repositories from `domain` to `infra/persistence` while preserving public re-exports.
2. Split task record persistence, default/schema mapping, strategy projection, and worktree document mirroring into separate collaborators.
3. Preserve atomic replacement, directory fsync, file locking, stale-update detection, path containment, and malformed-record handling.
4. Route task creation, load/list/update, agent registration/update/list, and document synchronization through application ports.
5. Run adapter contract tests against real temporary repositories and in-memory fakes.

Exit gate: `domain` has no persistence import; task and agent JSON fixtures and concurrency behavior remain identical.

Rollback: stable `state.py` and `agents.py` facades can point back to the legacy implementation until the phase is merged.

### Phase 5 - Migrate Planning, Lifecycle, And Workflow Use Cases

1. Convert approve/request-changes/revise/freeze/generate operations into application use cases depending on ports and pure domain policies.
2. Remove the planning -> lifecycle guard -> lifecycle rules -> planning cycle; lifecycle policy consumes domain values, never the public planning facade.
3. Convert workflow advancement into a typed decision step followed by explicit effect execution.
4. Inject task repository, provider, verifier, closeout, conformance, obligation, event, metric, and clock collaborators instead of importing root modules.
5. Preserve lifecycle action risk levels, human gates, conformance colors, event order, status updates, and retry behavior.
6. Keep `planning.py`, `workflow.py`, `lifecycle_guard.py`, and related public modules as delegating compatibility surfaces.

Exit gate: planning/workflow contract tests pass through both legacy and new application paths; targeted cycle edges and allowlist entries reach zero.

Rollback: composition wiring returns the affected use case to the legacy adapter without changing task records.

### Phase 6 - Move Workspace, Provider, Verification, Event, And Artifact Effects

1. Move `gitops` and worktree mechanics behind `WorkspacePort` while retaining security containment and rollback tests.
2. Move provider launch and local model implementations behind `ProviderPort`; remove provider-to-CLI imports and handler calls.
3. Separate verification policy from command execution. Domain/application decide what must be verified; the infra verifier executes bounded commands and returns typed evidence.
4. Move JSONL/noop event implementations behind `EventPublisherPort` and repository artifact IO behind `ArtifactStorePort`.
5. Preserve process environment, command argument handling, timeout behavior, receipt schemas, event envelopes, and local-agent safety constraints.

Exit gate: application/domain contain no Git, subprocess, MCP, CLI, or provider implementation imports; end-to-end request -> worktree -> provider -> verify characterization tests pass.

Rollback: each adapter is wired independently, so the last migrated effect can be reverted without reverting prior ports.

### Phase 7 - Separate Promotion Policy From Git And GitHub

1. Extract promotion eligibility, base resolution, retarget requirements, and receipt decisions into pure domain/application policy.
2. Implement Git operations through `VersionControlPort` and PR operations through `PullRequestPort`.
3. Model commit, push, PR open, merge record, child retarget, and closeout as explicit application steps with retry-safe state checks.
4. Preserve draft defaults, branch/base selection, receipt shape, side-effect ordering, and failure recovery.
5. Replace facade monkeypatch synchronization with injected fakes in tests.

Exit gate: promotion policy tests run without Git or `gh`; adapter integration tests prove the existing repository workflow and receipts.

Rollback: promotion remains behind its existing public facade and can be switched back as one unit before merge.

### Phase 8 - Rewire Interfaces And Bound Evolution

1. Make CLI handlers and MCP tools/resources call application commands and query services rather than top-level implementation functions.
2. Reduce `interfaces/cli/app.py` and `interfaces/mcp/service.py` to repository-root resolution, request adaptation, dispatch, tracing, and presentation.
3. Keep public modules and `compat` as explicit re-exports/delegators; remove `sys.modules` aliasing where identity compatibility tests allow it.
4. Make `evolution` consume read/query ports, evaluation ports, and append-only artifact ports. It may recommend or request work but may not approve, freeze, verify, activate, promote, or mutate canonical task authority.
5. Split oversized evolution harness responsibilities into planning, execution, materialization, receipt, and projection modules only where the split corresponds to a tested boundary.
6. Verify that CLI help, exit codes, MCP definitions, resource URIs, trace records, and Python imports remain stable.

Exit gate: interfaces have no direct infra/persistence imports; public compatibility and evolution authority tests pass.

Rollback: stable facades continue to expose the old call signatures while interface wiring can revert independently.

### Phase 9 - Remove Transitional Debt And Synchronize Documentation

1. Remove all architecture-test allowlist entries and verify that no forbidden cross-layer imports or cycles remain.
2. Remove dead legacy implementations only after repository-wide import search and installed-wheel tests prove no consumer remains.
3. Replace facade-specific monkeypatch tests with port contract and composition tests while retaining public compatibility assertions.
4. Update `docs/architecture.md` and relationship diagrams to describe only implemented, verified boundaries.
5. Record an architecture decision explaining dependency direction, mapper ownership, compatibility lifetime, and evolution authority.
6. Perform a final code review focused on under-abstraction, over-abstraction, side-effect order, concurrency, schema drift, and test gaps.

Exit gate: architecture tests are strict with no baseline exemptions; documentation matches code; no public behavior or persisted schema drift is found.

Rollback: documentation and dead-code removal are separate commits after runtime parity is already green.

### Phase 10 - Final Verification And Promotion

1. Rebase or merge the latest `main` before final verification and rerun all parity evidence after conflict resolution.
2. Run targeted domain, use-case, adapter, interface, security, evolution, and promotion suites.
3. Run the full Python 3.11-3.14 CI matrix, branch coverage threshold, lock check, source/wheel build, offline build when the build cache is available, and installed-wheel smoke tests outside the source tree.
4. Run Sisyphus spec validation, conformance review, verify, and an independent architecture review.
5. Commit each independently green migration slice, push, open reviewable PRs, require CI, merge in dependency order, record merge receipts, and close the parent task only after the final main-branch verification.

Exit gate: all acceptance criteria and verification mappings are satisfied on merged `main`, not only on the task branch.

## Delivery Slices

The preferred delivery is a parent architecture task with sequential child tasks/PRs:

1. Baseline and architecture guardrails.
2. Typed domain kernel and mappers.
3. Application ports and composition root.
4. Task/agent/document persistence migration.
5. Planning/lifecycle/workflow migration.
6. Workspace/provider/verifier/event/artifact adapters.
7. Promotion split.
8. Interface/evolution rewiring and cleanup.

Each child starts from freshly fetched and fast-forwarded `main`, owns a disjoint documented scope, and merges only after its parity gate passes. Stacked PRs are used only when a later slice cannot compile independently against main.

## Risks

| Risk | Impact | Mitigation | Rollback signal |
| --- | --- | --- | --- |
| mutable task dictionaries hide undocumented fields | mapper drops state or changes behavior | unknown-field round-trip fixtures and golden records before typed conversion | any byte/dictionary parity mismatch |
| facade identity and monkeypatch behavior is externally relied upon | downstream tests or scripts break | retain explicit shims and characterize public symbols before rewiring | installed-wheel compatibility failure |
| side-effect order changes during orchestration split | partial Git/provider/promotion states differ | sequence tests and failure injection at every effect boundary | receipt or task phase differs from baseline |
| file locking or stale-write behavior regresses | concurrent task updates are lost | shared repository contract tests and multi-process integration tests | stale update is accepted or atomicity test fails |
| new ports become one-method wrappers with no value | excessive indirection | introduce ports only for side effects/nondeterminism and review every port consumer count | port has no replaceable boundary or contract test |
| typed model becomes a second schema authority | domain/storage schemas drift | one canonical mapper per persisted aggregate and no entity `to_dict()` | duplicate serialization logic appears |
| architecture allowlist becomes permanent | migration stops halfway | every exemption has an owner/removal phase; final gate requires zero exemptions | violation count fails to decrease at a phase gate |
| evolution accidentally gains lifecycle authority | safety boundary weakens | explicit authority tests and application query/append-only ports | evolution can approve/freeze/verify/promote canonical state |
| very large PR obscures regressions | review and rollback become unsafe | mergeable child tasks/PRs with phase-specific evidence | a slice cannot be reviewed or reverted independently |

## Non-Goals

- splitting Sisyphus into network services or Docker containers
- replacing repository-local state with a database or event-sourced system
- changing the `sisyphus` package/distribution name
- redesigning task JSON, MCP schemas, CLI grammar, lifecycle policy, or artifact protocols
- adding a dependency-injection framework, ORM, or runtime schema framework
- merging the separate Sisyphus Harness Hermes/GEPA/model-benchmark roadmap into this repository refactor
- abstracting pure functions or standard-library data transformations that do not cross a real boundary

## Design Evaluation

- Design Mode: `full`
- Decision Reason: `introduces an explicit application layer, reverses persistence and execution dependencies, and changes authority ownership across the core runtime`
- Confidence: `high`
- Layer Impact: `layer-adding`
- Layer Decision Reason: `adds inward-owned application ports and a composition root while moving concrete side effects outward`
- Required Design Artifacts: `connection_diagram, sequence_diagram, boundary_note`

## Design Artifacts

- Connection Diagram: `design/dependency-boundary.md`
- Sequence Diagram: `design/migration-sequence.md`
- Boundary Note: `design/authority-boundary.md`

## Test Strategy

### Normal Cases

- [ ] Existing Python, CLI, and MCP task workflows produce equivalent results through the new application use cases.
- [ ] Existing task and agent records round-trip through centralized mappers without shape or extension-field loss.
- [ ] Planning, workflow, verification, and promotion complete through injected concrete adapters with unchanged receipts and events.

### Edge Cases

- [ ] Legacy records with missing defaults or unknown fields remain readable and are preserved on update.
- [ ] Empty verification profiles, disabled event publishing, stale agent records, and tasks without promotion remain compatible.
- [ ] Compatibility facades and installed-wheel imports continue to expose the documented public surface during every migration slice.

### Exception Cases

- [ ] Concurrent stale updates, malformed JSON, unsafe paths, and symlink escapes fail with existing safe behavior.
- [ ] Provider, verifier, Git, GitHub, event, and artifact failures leave retryable state and do not skip lifecycle gates.
- [ ] Architecture tests reject new outward domain/application imports, cross-boundary cycles, and business logic added to facades.

## Verification Mapping

- `Existing Python, CLI, and MCP task workflows produce equivalent results through the new application use cases.` -> `characterization, interface structure, MCP core, and end-to-end workflow test suites`
- `Existing task and agent records round-trip through centralized mappers without shape or extension-field loss.` -> `task/agent mapper contract tests using committed golden fixtures`
- `Planning, workflow, verification, and promotion complete through injected concrete adapters with unchanged receipts and events.` -> `application use-case contract tests plus temporary Git repository integration tests`
- `Legacy records with missing defaults or unknown fields remain readable and are preserved on update.` -> `legacy record compatibility and unknown-field round-trip tests`
- `Empty verification profiles, disabled event publishing, stale agent records, and tasks without promotion remain compatible.` -> `edge-case unit and integration matrix for audit, events, agents, and promotion`
- `Compatibility facades and installed-wheel imports continue to expose the documented public surface during every migration slice.` -> `tests.test_interface_structure plus isolated installed-wheel smoke script`
- `Concurrent stale updates, malformed JSON, unsafe paths, and symlink escapes fail with existing safe behavior.` -> `persistence concurrency, inbox validation, and path security suites`
- `Provider, verifier, Git, GitHub, event, and artifact failures leave retryable state and do not skip lifecycle gates.` -> `failure-injection adapter contract and orchestration sequence tests`
- `Architecture tests reject new outward domain/application imports, cross-boundary cycles, and business logic added to facades.` -> `tests.test_architecture_dependencies with zero final exemptions`

## External LLM Review

- Required: `yes`
- Provider: `independent Codex reviewer`
- Purpose: `independent challenge of dependency direction, compatibility evidence, abstraction balance, and hidden side-effect regressions`
- Trigger: `after all migration tests pass and before final promotion`
