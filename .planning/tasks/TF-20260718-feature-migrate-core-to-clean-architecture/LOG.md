# Log

## Timeline

- 2026-07-19: Created the planning-first Clean Architecture migration task from current `main`.
- 2026-07-19: Read canonical observation, record, conformance, brief, plan, verify, and log resources.
- 2026-07-19: Replaced the generic plan with a full layer-adding migration design and rollback gates.
- 2026-07-19: Spec validation passed, the operator-directed plan was approved, the spec was frozen, and nine execution subtasks were generated.
- 2026-07-19: Recorded a 497-test baseline and 82.8% branch-aware coverage before runtime changes.
- 2026-07-19: Added architecture fitness tests and removed the planning/lifecycle import cycle.
- 2026-07-19: Moved lifecycle decisions into a pure typed domain policy while preserving the public dict gate shape.
- 2026-07-19: Added centralized Task/Agent record mappers with unknown-field and key-order preservation.
- 2026-07-19: Moved concrete Task/Agent repositories to infra/persistence and retained the legacy import paths as compatibility shims.
- 2026-07-19: Added application repository ports, typed query services, concrete JSON adapters, and bootstrap.py.
- 2026-07-19: Passed the expanded full suite with 527 tests after the first migration slice.
- 2026-07-19: Extracted planning gate authority into pure domain models and policies and delegated lifecycle decisions to them.
- 2026-07-19: Moved planning, workflow, task factory, promotion, and spec-validation implementations out of domain into infra adapters.
- 2026-07-19: Replaced Inbox model serialization methods with a strict interface parser and centralized record mapper.
- 2026-07-19: Removed all domain outward dependencies and all static internal import cycles; architecture tests now enforce both without allowlists.
- 2026-07-19: Passed the expanded full suite with 535 tests after the second migration slice.
- 2026-07-19: Replaced workflow's direct side-effect imports with an application use case and explicit task, planning, obligation, conformance, provider, verification, closeout, event, and intervention ports.
- 2026-07-19: Preserved the public workflow facade and provider-runner patch point through bootstrap composition.
- 2026-07-19: Passed the expanded full suite with 542 tests after the workflow application slice.
- 2026-07-19: Moved pure design normalization, assessment, and freeze rules into domain/task and retained Markdown loading in the public adapter.
- 2026-07-19: Replaced planning's direct persistence and filesystem orchestration with an application use case using task, document, validation, design-conformance, intervention, and clock ports.
- 2026-07-19: Split planning and workflow composition roots to prevent eager adapter imports from recreating an audit/planning cycle.
- 2026-07-19: Passed the expanded full suite with 547 tests after the planning application slice.
- 2026-07-19: Replaced audit.py orchestration with a typed Verification application service, ArtifactRef/CommandExecution receipts, and document, command, conformance, evidence, event, repository, validation, and clock ports.
- 2026-07-19: Preserved VerifyOutcome, verify Markdown, evidence graph, event payloads, command result records, and lifecycle behavior through the public audit facade.
- 2026-07-19: Re-anchored the bounded evolution review-gate target to its new verification-policy owner instead of the audit facade.
- 2026-07-19: Passed the expanded full suite with 552 tests after the verification application slice.
- 2026-07-19: Moved promotion execution and merge-receipt orchestration behind application ports for version control, pull requests, artifacts, closeout, conformance, intervention, and reopened-task events.
- 2026-07-19: Retained the public promotion facade, GitOperationError contract, GitHub CLI patch point, receipt paths, changeset projection, and stacked-child retarget behavior.
- 2026-07-19: Added direct PromotionService tests and passed the expanded full suite with 556 tests after the promotion application slice.
- 2026-07-19: Split tracked Agent execution into an application-owned registration/start/heartbeat/finalization use case and an infra-owned UTF-8 subprocess adapter.
- 2026-07-19: Preserved command launch, environment merge, output summary, heartbeat failure, interrupt cancellation, process-start failure, and public AgentTrackingError behavior.
- 2026-07-19: Added failure-injection AgentExecutionService tests and passed the expanded full suite with 561 tests after the Agent process slice.
- 2026-07-19: Moved Agent ID/status/staleness/timestamp rules into the domain and Agent registration/update/query orchestration into AgentManagementService.
- 2026-07-19: Reused AgentManagementService directly for tracked execution, deleting the transitional callback adapter instead of retaining redundant abstraction.
- 2026-07-19: Added unknown agent-field persistence coverage and passed the expanded full suite with 566 tests after the Agent management slice.
- 2026-07-19: Moved worker plan/spec authorization into AgentLaunchService and reduced the CLI Agent handler to command adaptation and presentation.
- 2026-07-19: Rewired CLI and MCP Agent reads/writes through AgentManagementService while preserving the existing MCP function-injection signatures.
- 2026-07-19: Added Agent launch gate-order tests and passed the expanded full suite with 570 tests after the Agent interface slice.
- 2026-07-19: Removed the Provider wrapper's normal CLI reverse dependency; provider launches now invoke AgentLaunchService directly.
- 2026-07-19: Retained explicit public CLI runner overrides as a compatibility hook and added an architecture regression test prohibiting Provider-to-CLI imports.
- 2026-07-19: Passed the expanded full suite with 572 tests after the Provider launch rewiring slice.
- 2026-07-19: Moved conformance defaults and task-strategy parsing into pure task-domain modules, removing five facade symbol dependencies from the legacy task repository.
- 2026-07-19: Removed the Agent facade's concrete repository dependency and restored the two pre-migration domain repository import paths as identity-preserving, import-only shims.
- 2026-07-19: Tightened the architecture baseline to exactly those two shim edges and documented the remaining implementation debt with removal and verification gates.
- 2026-07-19: Passed 47 persistence/interface/mapping contracts and the expanded full suite with 575 tests after the repository compatibility slice.
- 2026-07-19: Moved WorkspaceExecutor into `infra/workspace`, introduced the inward WorkspacePort action contract, and retained the provider import path as an identity-preserving outer shim.
- 2026-07-19: Replaced path-based workspace reads/writes with descriptor-relative no-follow traversal, durable atomic replacement, resolved protected-path checks, and symbolic-link patch rejection.
- 2026-07-19: Added protected alias and resolve/open race regressions and passed the expanded full suite with 580 tests after the Workspace adapter slice.
- 2026-07-19: Moved Workspace mutation ordering and completion eligibility into the pure `domain/agent/workspace.py` state model while preserving the provider facade's result shape.
- 2026-07-19: Passed 27 focused Workspace/architecture regressions and the expanded full suite with 583 tests after activating descriptor-relative I/O and extracting Workspace policy.
- 2026-07-19: Extracted Git and configured-test subprocesses behind infra-local Workspace effect contracts without leaking Git concepts into the application port.
- 2026-07-19: Added real-adapter, injected-failure, timeout, and invalid-patch classification tests; passed 31 focused regressions and the expanded full suite with 587 tests.
- 2026-07-19: Split provider wrapper argument parsing into `interfaces/provider_wrapper` and moved launch construction plus receipt finalization/persistence into focused infra adapters while retaining legacy patch points as delegates.
- 2026-07-19: Added typed parser, launch identity, receipt cleanup/callback, and facade ownership guards; passed 37 focused regressions and the expanded full suite with 592 tests.
- 2026-07-19: Moved noop/JSONL event publishing into `infra/events`, removed infra dependencies on public config/event facades, and routed verification document writes through the atomic artifact store.
- 2026-07-19: Replaced sidecar event read locks after the full suite exposed read-only Evolution mutations; descriptor locking, `O_EXCL`, `O_NOFOLLOW`, file/directory fsync, and read-only regressions now pass.
- 2026-07-19: Passed 59 focused event/artifact/persistence/interface/architecture regressions and the expanded full suite with 597 tests.
- 2026-07-19: Moved task-record construction and save ordering behind `CreateTaskRecordCommand`, `TaskRecordCreationService`, and a dedicated composition root while preserving the public `state.py` surface.
- 2026-07-19: Relocated the file task-record adapter to canonical persistence ownership, added application/facade/identity contracts, and passed the expanded full suite with 600 tests.
- 2026-07-19: Added descriptor-relative Workspace tree fingerprints and a tree-hash mutation guard around patch execution; undeclared, protected, symlink/special-file, no-op, and partial-failure mutations cannot be recorded as successful Agent work.
- 2026-07-19: Added real and injected patch postcondition regressions and passed the expanded full suite with 603 tests.
- 2026-07-19: Replaced unbounded verification subprocess calls with a strict single-line command parser, process-group timeout, bounded output tail, and typed duration/timeout receipts while retaining shell command compatibility.
- 2026-07-19: Moved conformance entry mutation into the task domain and evidence graph construction behind `VerificationEvidencePort`; verification/lifecycle adapters no longer import public conformance, evidence, gate, promotion-state, or state facades.
- 2026-07-19: Added timeout, output-bound, early-EOF, evidence parity, clock injection, and architecture regressions and passed the expanded full suite with 611 tests.
- 2026-07-19: Extracted canonical local-provider config, validation, availability, and worker-command construction; provider launch now receives prompt builders and no longer imports public prompt/provider facades.
- 2026-07-19: Bound new local-agent receipts to stable request and receipt digests, added a bounded no-follow strict parser plus atomic persistence, and retained digest-less v1 fixture compatibility through explicit parsing rules.
- 2026-07-19: Injected episode recording at composition, added identity/tamper/symlink/request-binding regressions, and passed the expanded full suite with 617 tests.
- 2026-07-19: Moved document-backed test-strategy synchronization to `infra/documents` and rewired spec validation to domain design rules, application gate records, and the canonical task repository.
- 2026-07-19: Replaced Planning's public conformance-facade call with an injected-clock adapter over domain conformance mutation, added facade-dependency and design-anchor regressions, and passed the expanded full suite with 619 tests.

## Notes

- Current canonical conformance is green with zero drift at the latest design anchor.
- The plan intentionally separates the Sisyphus core refactor from the Sisyphus Harness Hermes/GEPA/model-execution roadmap.
- Public lifecycle_state, lifecycle_rules, Task/Agent repository imports, dictionary results, and persisted record extensions remain compatible.
- Domain implementation outward dependencies and static internal import cycles are zero. The only domain outward edges are the two explicitly guarded import-only repository compatibility shims.

## Follow-ups

- Execute the ordered debt ledger in `docs/clean-architecture-implementation-debt.md`, beginning with the remaining workflow/planning/spec-validation adapters and full creation/daemon/closeout use cases.
- Isolate Evolve candidate generation from Control-owned approval, signing, active-policy, and queue authority.
- Rewire remaining CLI/MCP consumers, validate architecture documentation, then run final package and merged-main verification.
