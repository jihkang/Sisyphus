# Clean Architecture Implementation Debt

Updated: 2026-07-20
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
| Boundary serialization ownership | Completed | Model-owned `to_dict`/`from_dict` and `to_json` methods were reduced from 14 methods across 10 modules to zero. Artifact, event, episode, search, evaluation, benchmark, and provider receipt wire shapes now live in explicit context codecs; the unused `ActionSpec.to_dict` path was deleted instead of replaced by an unused abstraction. Architecture guards reject mapping methods returning to any model, optional-field and JSONL framing regressions are covered, and the full 720-test suite is green |
| Hotspot responsibility review | Completed | Promotion execution and merge recording are separate command services behind the stable `PromotionService`; receipt and changeset projection is pure application code. Spec-validation IO delegates to filesystem-free application rules. Local-agent benchmark models, fixture parsing, execution, and rendering are separate modules while the legacy import and `_materialize_fixture` patch point remain stable. Verification Markdown/template projection is separate from the verify transaction. Focused boundary contracts, architecture reabsorption guards, and the full 730-test suite pass |
| Architecture and data-pipeline documentation | Completed | The architecture overview, implemented data pipeline, runtime relationship diagrams, and ADR 0001 now record dependency direction, mapping ownership, exact shim lifetime, lifecycle authority, canonical conformance colors, and the bounded Evolution role. Repository-hygiene tests resolve all local links, require current implementation anchors, and reject superseded ownership claims; the focused 46-test documentation and architecture set passes |

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

## Hotspot Review Decisions

Large files were evaluated by independent change reasons, side effects, callers,
and patch compatibility rather than by line count alone.

| Reviewed module | Decision | Current boundary and reason |
| --- | --- | --- |
| `application/use_cases/promotion.py` | Split | The 798-line service became a 91-line stable facade over `promotion_execution.py` and `promotion_merge.py`; `promotion_projection.py` owns receipt, changed-file, URL, and changeset projections. PR execution and merge/retarget now have separate command tests without changing construction or result identity |
| `providers/benchmark.py` | Split | The runner is 297 lines; fixture models, untrusted manifest parsing, and Markdown rendering moved to `benchmark_models.py`, `benchmark_fixtures.py`, and `benchmark_rendering.py`. Root imports preserve canonical identity and the private materialization patch point remains in the runner |
| `infra/validation/spec_validation.py` | Split | The 382-line adapter owns contained document reads, prerequisite record reads, fingerprints, report persistence, and task-state updates. `application/spec_validation_rules.py` owns deterministic policy and has direct no-filesystem tests |
| `application/use_cases/verification.py` | Split | The verify transaction remains 425 lines; `application/verification_projection.py` owns VERIFY Markdown and template-marker detection. The service still owns one ordered gate/command/evidence/save/event transaction |
| `interfaces/cli/app.py` | Retain | The 784-line file is an intentionally stable compatibility surface made of delegating handler wrappers plus one dynamic handler registry. Command grammar, implementation handlers, and renderers are already split; another wrapper split would break supported monkeypatch lookup without isolating policy |
| `application/use_cases/planning.py` | Retain | Its approve, request-changes, revise, freeze, and subtask operations form one planning review/spec state machine over the same ports and gate invariants. There is no persistence, subprocess, or transport effect to extract |
| `interfaces/inbox/parser.py` | Retain | All public entry points share one strict inbound JSON budget, exact-type rules, size limits, and repository-relative path policy. Splitting primitive validators would duplicate security invariants across payload parsers |
| `evolution/harness.py` | Retain | The harness is now effect-free and owns only evaluation plans, metrics, evidence requests, and worktree command projections. Task authority and worktree/process effects already live in control-owned composition and infrastructure |

Retained modules must be reconsidered only when they gain a second authority,
an external effect, or a change reason that can be tested independently. Line
growth by itself is not a trigger.

## Remaining Implementation Debt

Current accounting: `0` High implementation items, exactly `2` accepted import
compatibility shims, `0` Medium implementation items, and `1` release gate. The
two shims are intentionally excluded from implementation debt because they own
no behavior; they remain tracked compatibility debt until their retirement
conditions are met.

| ID | Priority | Boundary and current evidence | Required end state | Verification gate |
| --- | --- | --- | --- | --- |
| CA-11 | Release gate | Final coverage, wheel/offline build, independent review, PR/CI/merge, merge receipt, and merged-main validation are not complete | Run the frozen verification matrix after integrating latest `main`, then promote and verify the merged commit | Coverage >=80%, wheel install smoke, Sisyphus verify green, CI green, merge recorded, and tests green on updated `main` |

## Execution Order

1. Run the full verification and promotion sequence on the latest `main`.

This order follows dependency direction: outer effects must be injectable before
orchestrators and interfaces can stop importing their implementations.
