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

## Notes

- Current canonical conformance is green with zero drift at the latest design anchor.
- The plan intentionally separates the Sisyphus core refactor from the Sisyphus Harness Hermes/GEPA/model-execution roadmap.
- Public lifecycle_state, lifecycle_rules, Task/Agent repository imports, dictionary results, and persisted record extensions remain compatible.
- Domain outward dependencies and static internal import cycles are both zero under the architecture fitness tests.

## Follow-ups

- Separate workspace/provider execution from Agent policy and process state.
- Isolate Evolve candidate generation from Control-owned approval, signing, active-policy, and queue authority.
- Rewire remaining CLI/MCP consumers, validate architecture documentation, then run final package and merged-main verification.
