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
| Repository request interface path | Completed | `RepositoryRequestService` owns queue -> process -> workflow-until-stable -> task-load ordering and merge-event result projection; CLI ingest and MCP task tools use the composition root, with focused application tests and the full 659-test suite green |
| Command and status interface paths | Completed | Planning/spec-validation, verification/closeout, task creation, daemon/service runtime, status queries, and promotion execution now enter through application services assembled by composition; spec-validation outcome ownership moved inward, service polling has focused application tests, existing public patch points remain compatible, and the full 666-test suite is green |
| Search and ContextPack query path | Completed | Search documents and deterministic retrieval are application-owned; repository projection, JSONL indexing, and contained atomic ContextPack persistence are infrastructure-owned; CLI and MCP enter through composition while four public modules remain import-only identity facades. Focused application, interface, path-security, and architecture guards pass, and the full 676-test suite is green |
| Event, metrics, and repository status path | Completed | Event envelopes and metric calculations are application-owned projections; task/event reads and durable metric event appends are infrastructure-owned; MCP repository resources use composed status queries instead of flat event/metric facades. Public `events.py` and `metrics.py` remain import-only identity surfaces, focused security/dependency tests pass, and the full 681-test suite is green |
| Lifecycle action, observation, and evidence query path | Completed | Lifecycle record projection and action registry policy are inward-owned while concrete record mapping is composition-owned; observation and evidence summaries are pure application projections over precomputed boundary inputs; required-document and evidence JSON IO live in infrastructure. Public lifecycle/action/observation/evidence modules remain import-only identity facades, unnecessary evidence reads preserve their prior short-circuit behavior, and the full 688-test suite is green |
| Episode trace boundary | Completed | Episode records, state diffs, validation, and trace checks are application-owned; `EpisodeTracePort` exposes append/read/next-step behavior; the repository store owns no-follow JSONL IO and contained paths; MCP and CLI use composition instead of the flat module. Explicit step injection avoids repeated scans for multi-event provider receipts, malicious IDs and symlink escapes are rejected, and the full 693-test suite is green |
| Artifact resource query boundary | Completed | `FeatureArtifactResourceService` owns resource selection and public payload shape over `FeatureArtifactQueryPort`; repository projection, snapshot status, and obligation reads are supplied by an infra adapter. MCP task resources use composition, the legacy module is import-only, call-order and snapshot-preference tests pass, and the full 699-test suite is green |
| Evolution read, handoff, projection, and run-artifact boundaries | Completed | Dataset extraction, follow-up task reads, execution/verification projection, and decision events use read-only task/event ports; follow-up creation accepts only a request-only command with `auto_run=False`; run artifacts use a validated append-only store with exclusive creation, no-follow bounded reads, containment, and fsync. CLI/MCP use composition, surface/event modules are import-only facades, authority/path guards pass, and the full 708-test suite is green |
| Evolution evaluation authority and worktree effects | Completed | `evolution/harness.py` now owns only plans, metrics, requests, and command projections. Control-owned composition performs task request, plan approval, spec freeze, and provider ordering; infrastructure owns bounded mutation materialization, process execution, atomic output/receipt persistence, containment, and symlink rejection. Authority and path-security guards pass, and the full 711-test suite is green |
| Artifact, DSL, snapshot, and execution-policy ownership | Completed | Artifact and DSL value models are domain-owned without boundary mapping methods; pure projection, evaluation, obligation, snapshot, and execution-policy decisions are application-owned; explicit codecs own wire shapes; package declaration reads and secure document/snapshot IO are infrastructure-owned; default declaration selection is composed outside the inner layers. The seven stable root modules are import-only facades, infrastructure imports only canonical owners, symlink regressions are covered, and the full 716-test suite is green |

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

Current accounting: `0` High implementation items, exactly `2` accepted import
compatibility shims, `3` Medium implementation items, and `1` release gate. The
two shims are intentionally excluded from implementation debt because they own
no behavior; they remain tracked compatibility debt until their retirement
conditions are met.

| ID | Priority | Boundary and current evidence | Required end state | Verification gate |
| --- | --- | --- | --- | --- |
| CA-08 | Medium | There are 14 model-owned `to_dict`/`from_dict` methods across 10 non-domain modules. They are an audit inventory, not 14 automatically equivalent mappings | Move wire mapping to explicit codecs only where records share a real schema boundary; retain specialized mapping when omission rules, digests, compatibility, or presentation differ | Golden wire fixtures, unknown-field behavior, digest fixtures, and round-trip tests pass before each method is removed |
| CA-09 | Medium | The current review hotspots are `application/use_cases/promotion.py` (798), `interfaces/cli/app.py` (784), `providers/benchmark.py` (729), `infra/validation/spec_validation.py` (701), `application/use_cases/planning.py` (600), `interfaces/inbox/parser.py` (572), `evolution/harness.py` (557), and `application/use_cases/verification.py` (523). Size alone is not a violation, but each is a candidate for mixed change reasons | Split only along demonstrated policy, orchestration, parsing, presentation, or replaceable-effect boundaries; do not create one-method ports or generic manager classes | Every extracted boundary has a distinct change axis and focused contract tests; modules found cohesive are documented and intentionally retained |
| CA-10 | Medium | `docs/architecture.md` describes the pre-migration staged layout and lacks the implemented application/composition dependency flow | Update architecture and data-pipeline diagrams only after runtime boundaries are final; add an ADR for dependency direction, mapper ownership, shim lifetime, and Evolve authority | Documentation path checks and an implementation-to-document conformance review pass |
| CA-11 | Release gate | Final coverage, wheel/offline build, independent review, PR/CI/merge, merge receipt, and merged-main validation are not complete | Run the frozen verification matrix after integrating latest `main`, then promote and verify the merged commit | Coverage >=80%, wheel install smoke, Sisyphus verify green, CI green, merge recorded, and tests green on updated `main` |

### CA-08 Serialization Inventory

| Module | Methods | Disposition to prove |
| --- | ---: | --- |
| `test_first.py` | 2 | Compare the two result projections before introducing a codec |
| `benchmark.py` | 1 | Keep separate from provider benchmark records unless golden payloads prove one schema |
| `providers/benchmark.py` | 2 | Extract only the benchmark wire boundary shared by persistence/reporting consumers |
| `providers/local_agent.py` | 1 | Preserve provider receipt omission and compatibility rules |
| `eval/loop.py` | 1 | Preserve evaluation result metrics and ordering |
| `application/episode_trace.py` | 1 | Move only if the trace store is the actual wire owner |
| `application/events.py` | 1 | Move only if all event publishers consume the same envelope codec |
| `application/action_space.py` | 1 | Distinguish lifecycle projection from persisted records |
| `application/search/retrieval.py` | 1 | Treat ranked-result presentation separately from indexed-document storage |
| `application/search/models.py` | 3 | Consolidate the `SearchDocument` encode/decode pair while preserving search-result and ContextPack projections |

The inventory is enforced indirectly by the domain-model mapping guard: no new
`to_dict`/`from_dict` method may move into `domain`. CA-08 is complete only after
each remaining method is either moved to a named codec or explicitly retained
with a documented boundary reason.

## Execution Order

1. Audit the 14 remaining serialization methods against golden wire contracts and
   extract only genuinely shared codecs.
2. Review the CA-09 hotspots for independent change axes and split only the
   boundaries that have focused contract evidence.
3. Synchronize architecture/data-pipeline documentation and record the dependency,
   mapper, shim-lifetime, and Evolve-authority ADR.
4. Run the full verification and promotion sequence on the latest `main`.

This order follows dependency direction: outer effects must be injectable before
orchestrators and interfaces can stop importing their implementations.
