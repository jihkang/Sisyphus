# Clean Architecture Implementation Debt

Updated: 2026-07-19
Scope: `TF-20260718-feature-migrate-core-to-clean-architecture`

This ledger records the remaining implementation debt on the Clean Architecture
migration branch. It distinguishes temporary import compatibility from runtime
code that still owns the wrong responsibility. A large module is not debt by
itself; it is listed only when it also mixes independently testable authorities or
side effects.

The separate Sisyphus Harness roadmap, including Hermes, GEPA, Docker service
separation, and real 30.5B model evidence, is not part of this repository migration.

## Debt Accounting Rule

- Domain and application implementation code may depend only inward.
- Interfaces may invoke application commands and queries, but may not select
  concrete infrastructure.
- Stable legacy imports may remain only as explicit, identity-preserving shims.
- A compatibility shim may contain a module docstring, explicit imports, and a
  literal `__all__`. It may not contain functions, classes, conditions, or mutable
  runtime state.
- Every allowed edge must have a named retirement condition. New edges are test
  failures, not additions to a broad baseline.

## Closed In The Current Slice

| Item | Result | Evidence |
| --- | --- | --- |
| Task repository outward imports | Removed five facade symbol dependencies by moving conformance and strategy normalization inward and importing design/promotion rules from their domain owners | `infra/persistence/task_repository.py` now imports only domain, shared, and sibling persistence modules |
| Agent facade concrete dependency | Removed | `agents.py` derives the compatibility record path through `shared.paths.agent_dir` instead of importing the concrete agent repository |
| Legacy repository imports | Restored without restoring implementation ownership | The two modules listed below preserve object identity with the infrastructure implementations |
| Persistence/interface/mapping parity | Passed | 47 tests across `test_persistence`, `test_interface_structure`, and `test_record_mappers` |
| Workspace location, policy, and file safety | Completed | Canonical implementation moved to `infra/workspace`; application owns the action port; domain owns mutation/completion policy; descriptor-relative reads/writes reject symlink races and fsync atomic replacements |
| Workspace process effects | Completed | `WorkspaceGitEffects` and `WorkspaceTestEffects` isolate Git and configured-test subprocesses with real-adapter and failure-injection tests |
| Provider wrapper responsibilities | Completed | Typed parsing lives in `interfaces/provider_wrapper`; launch construction and receipt finalization/persistence are separate infra modules; the public wrapper retains only dispatch, application launch, and compatibility delegates |
| Event publishing | Completed | Canonical noop/JSONL publishers live in `infra/events`; JSONL append uses descriptor locking, identity-preserving public facades, file and creation-directory fsync, atomic create detection, and no-follow leaf opens |
| Verification/artifact document writes | Completed | Verification documents delegate to the canonical atomic `RepositoryArtifactStore`; infra imports the canonical config loader instead of the public config facade |
| Task-record creation boundary | Completed | `CreateTaskRecordCommand`, `TaskRecordCreationService`, and the composition root own construction and persistence ordering; `state.py` delegates creation and preserves identity-compatible repository exports |
| Workspace patch containment | Completed | Descriptor-relative tree snapshots hash regular files, modes, symlink targets, and special-file identity before and after `git apply`; only declared non-protected regular-file transitions are accepted, and partial-failure mutations are quarantined |
| Verifier, conformance, and evidence effects | Completed | Verification commands use a strict single-line parser, process-group timeout, bounded output tail, and typed receipts; conformance mutation is domain-owned; evidence construction is application-owned and atomically persisted through `VerificationEvidencePort` |
| Provider launch and receipt boundary | Completed | Local-provider config/validation/availability/command construction are canonical infra responsibilities; prompt builders are injected; new launches bind signed receipts to stable request digests; bounded no-follow parsers and atomic persistence reject malformed, oversized, symlinked, or tampered receipts while retaining digest-less v1 compatibility |
| Planning and spec-validation adapters | Completed | Document-backed strategy sync lives in `infra/documents`; spec validation imports domain design rules, application gate records, and canonical persistence directly; design anchors use injected time and domain conformance mutation without public-facade imports |
| Workflow conformance boundary | Completed | Conformance policy/projections and injected time/ID record mutation live in `application/conformance_records.py`; Markdown projection lives in `infra/documents`; workflow and planning adapters share the application service; Evolution targets the canonical policy source rather than the facade |
| Closeout orchestration | Completed | `CloseoutService` owns lifecycle/evidence/dirty-check ordering, state transitions, events, and intervention requests over explicit ports; workflow and promotion compose the same service; `closeout.py` preserves the public function and dirty-check patch point |
| Obligation convergence orchestration | Completed | Queue→execute→snapshot ordering and max-step policy live in `ObligationConvergenceService`; verification is injected into the infra runtime; queue writes are atomic; the workflow adapter has zero root-facade dependencies and the public obligation module preserves result identity and function signatures |
| Task workspace creation | Completed | `TaskWorkspaceCreationService` owns duplicate detection, worktree/task-directory provisioning order, persistence, template materialization, and rollback policy over narrow workspace/template ports; `creation.py` is an import-compatible facade and preserves its template patch point |
| Inbox and daemon orchestration | Completed | Queue creation, strict parsing, claim/process/complete/fail transitions, quarantine, retry recovery, statistics, and polling live in separate application services; conversation and PR-merge handlers own their explicit effect order over ports; daemon logs share the locked, no-follow, file/directory-fsync JSONL primitive; `daemon.py` is a 195-line compatibility facade instead of a 902-line orchestrator; the full 654-test suite passes |
| Provider-to-daemon dependency | Removed | Conversation provider execution receives queue and processing services explicitly; architecture guards reject both direct and dynamic `sisyphus.daemon` dispatch and reject concrete persistence/Git/promotion effects returning to the daemon facade |

## Accepted Domain Dependency Exceptions

These are the complete allowlist for outward imports from `domain`. They are
compatibility debt, not implementation debt. Outer public-path shims such as
`providers/workspace.py` do not reverse an inward dependency and therefore are
not entries in this allowlist; their retirement remains attached to the owning
implementation-debt item.

| Shim | Canonical implementation | Retirement condition |
| --- | --- | --- |
| `domain/agent/repository.py` | `infra/persistence/agent_repository.py` | Repository-wide import search and an installed-wheel compatibility window prove no supported consumer imports the old path |
| `domain/task/repository.py` | `infra/persistence/task_repository.py` | Repository-wide import search and an installed-wheel compatibility window prove no supported consumer imports the old path |

`tests/test_architecture_dependencies.py` requires the observed domain outward
edges to equal these two entries exactly and separately verifies that both files
remain import-only. Removing a shim requires shrinking the allowlist in the same
change.

## Remaining Implementation Debt

| ID | Priority | Boundary and current evidence | Required end state | Verification gate |
| --- | --- | --- | --- | --- |
| CA-05 | High | CLI and MCP handlers still import root implementations such as `state`, `planning`, `audit`, `closeout`, `creation`, and `daemon` | Route handlers through application command/query services assembled by composition roots; interfaces retain only adaptation, dispatch, trace, and rendering | CLI help/exit/output and MCP tools/resources/schema/trace fixtures remain identical; interfaces have no implementation imports |
| CA-07 | High | Evolution dataset, operator, receipts, and verification modules read canonical state directly; `evolution/harness.py` is 1,072 lines. Canonical obligation infra still imports flat artifact projection/evaluator/snapshot, DSL, and execution-policy modules | Expose read/query, evaluation, execution-policy, and append-only artifact ports; place artifact/DSL policy under explicit application/domain owners. Evolve may recommend/request work but cannot approve, freeze, verify, activate, promote, or mutate canonical authority | Authority tests prove forbidden actions are unreachable; baseline/candidate/obligation artifacts and existing MCP/CLI projections remain compatible |
| CA-08 | Medium | There are 58 model-owned `to_dict`/`from_dict` methods across 15 non-domain modules | Group only wire-shape-equivalent records under explicit codecs/mappers; retain custom mappers where schemas, omission rules, digests, or compatibility differ | Golden wire fixtures, unknown-field behavior, digest fixtures, and round-trip tests pass before each method is removed |
| CA-09 | Medium | Several modules mix multiple change reasons: `artifacts.py` (767), `providers/benchmark.py` (729), `dsl.py` (674), and large planning/verification/promotion use cases | Split only along demonstrated ownership or side-effect boundaries; do not create one-method ports or generic manager classes | Each extracted boundary has multiple meaningful consumers or a replaceable side effect and its own contract tests |
| CA-10 | Medium | `docs/architecture.md` describes the pre-migration staged layout and lacks the implemented application/composition dependency flow | Update architecture and data-pipeline diagrams only after runtime boundaries are final; add an ADR for dependency direction, mapper ownership, shim lifetime, and Evolve authority | Documentation path checks and an implementation-to-document conformance review pass |
| CA-11 | Release gate | Final coverage, wheel/offline build, independent review, PR/CI/merge, merge receipt, and merged-main validation are not complete | Run the frozen verification matrix after integrating latest `main`, then promote and verify the merged commit | Coverage >=80%, wheel install smoke, Sisyphus verify green, CI green, merge recorded, and tests green on updated `main` |

## Execution Order

1. Rewire CLI and MCP to application commands and queries.
2. Restrict Evolve to read/evaluation/append-only ports and add authority tests.
3. Consolidate serialization only where golden wire contracts prove equivalence.
4. Review oversized modules for real responsibility splits, then synchronize architecture documentation.
5. Run the full verification and promotion sequence on the latest `main`.

This order follows dependency direction: outer effects must be injectable before
orchestrators and interfaces can stop importing their implementations.
