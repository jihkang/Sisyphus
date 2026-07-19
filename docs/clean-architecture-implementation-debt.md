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
| CA-01 | High | `state.py` still combines task construction, directory creation, concrete persistence selection, and public compatibility | Move create/load/list/update coordination behind application commands and queries; leave `state.py` as a delegating facade | Task creation and legacy record fixtures remain byte/shape compatible; facade contains no branching business logic |
| CA-02 | High | Partial: `infra/workspace` owns secure file effects, `domain/agent/workspace.py` owns mutation/completion policy, and `WorkspacePort` is inward; `executor.py` still dispatches Git diff/apply and test subprocesses, and `git apply` cannot use the descriptor-relative file adapter | Isolate Git and test command execution as effect collaborators, give patch application an explicit containment contract, and retain `providers/workspace.py` only as an outer compatibility shim | Workspace contract, traversal, symlink, resolve/open race, patch-mode, mutation-order, timeout, output-bound, and effect failure-injection tests pass |
| CA-03 | High | `provider_wrapper.py` remains a 658-line parser, process launcher, receipt writer, compatibility patch surface, and presenter | Separate request parsing/presentation from provider execution and receipt persistence behind existing ports; preserve CLI override compatibility only at the facade | Provider failure-injection, environment, argument, receipt, CLI override, and installed-wheel tests pass |
| CA-04 | High | `daemon.py` is 902 lines and `creation.py`/`closeout.py` still coordinate queue, task state, worktrees, providers, verification, events, and promotion through root modules | Introduce application use cases for creation, daemon event handling, and closeout with narrow repository/effect ports; keep side-effect order explicit | Event replay, retry, gate, partial-failure, close, and end-to-end workflow characterization tests pass |
| CA-05 | High | CLI and MCP handlers still import root implementations such as `state`, `planning`, `audit`, `closeout`, `creation`, and `daemon` | Route handlers through application command/query services assembled by composition roots; interfaces retain only adaptation, dispatch, trace, and rendering | CLI help/exit/output and MCP tools/resources/schema/trace fixtures remain identical; interfaces have no implementation imports |
| CA-06 | High | Infrastructure adapters such as workflow, verification, task factory, and spec validation still call root facades; event and artifact stores are only partly port-backed | Make adapters depend on inward policy/record functions and implement event, artifact, verifier, Git, and worktree ports without calling public facades | Architecture test rejects adapter-to-facade edges; adapter contract and failure-injection suites pass |
| CA-07 | High | Evolution dataset, operator, receipts, and verification modules read canonical state directly; `evolution/harness.py` is 1,072 lines | Expose read/query, evaluation, and append-only artifact ports. Evolve may recommend/request work but cannot approve, freeze, verify, activate, promote, or mutate canonical authority | Authority tests prove forbidden actions are unreachable; baseline/candidate artifacts and existing MCP/CLI projections remain compatible |
| CA-08 | Medium | There are 58 model-owned `to_dict`/`from_dict` methods across 15 non-domain modules | Group only wire-shape-equivalent records under explicit codecs/mappers; retain custom mappers where schemas, omission rules, digests, or compatibility differ | Golden wire fixtures, unknown-field behavior, digest fixtures, and round-trip tests pass before each method is removed |
| CA-09 | Medium | Several modules mix multiple change reasons: `artifacts.py` (767), `providers/benchmark.py` (729), `dsl.py` (674), and large planning/verification/promotion use cases | Split only along demonstrated ownership or side-effect boundaries; do not create one-method ports or generic manager classes | Each extracted boundary has multiple meaningful consumers or a replaceable side effect and its own contract tests |
| CA-10 | Medium | `docs/architecture.md` describes the pre-migration staged layout and lacks the implemented application/composition dependency flow | Update architecture and data-pipeline diagrams only after runtime boundaries are final; add an ADR for dependency direction, mapper ownership, shim lifetime, and Evolve authority | Documentation path checks and an implementation-to-document conformance review pass |
| CA-11 | Release gate | Final coverage, wheel/offline build, independent review, PR/CI/merge, merge receipt, and merged-main validation are not complete | Run the frozen verification matrix after integrating latest `main`, then promote and verify the merged commit | Coverage >=80%, wheel install smoke, Sisyphus verify green, CI green, merge recorded, and tests green on updated `main` |

## Execution Order

1. Complete the remaining Workspace Git/test effects and the Provider, Verifier, Event, and Artifact adapter boundaries.
2. Move creation, daemon processing, and closeout orchestration into application use cases.
3. Rewire CLI and MCP to application commands and queries.
4. Restrict Evolve to read/evaluation/append-only ports and add authority tests.
5. Consolidate serialization only where golden wire contracts prove equivalence.
6. Review oversized modules for real responsibility splits, then synchronize architecture documentation.
7. Run the full verification and promotion sequence on the latest `main`.

This order follows dependency direction: outer effects must be injectable before
orchestrators and interfaces can stop importing their implementations.
