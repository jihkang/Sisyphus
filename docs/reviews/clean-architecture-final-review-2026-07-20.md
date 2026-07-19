# Clean Architecture Migration Final Review

- Review date: 2026-07-20
- Branch: `feat/migrate-core-to-clean-architecture`
- Base: current `origin/main` at review time
- Task: `TF-20260718-feature-migrate-core-to-clean-architecture`
- Review type: implementation self-review; the frozen independent-review gate is
  tracked separately and is not satisfied by this document

## Findings

No unresolved High or Medium implementation defect remains after the review
fixes below.

### Resolved High: support-file mirror could cross its boundary

`infra/persistence/task_repository.py` previously joined `task_dir` and `docs`
values directly, read through normal `Path` APIs, and wrote with `write_text`.
A manipulated document path, source symlink, or target-directory symlink could
therefore escape the intended task/worktree location.

Resolution:

- require relative POSIX task and document paths
- use bounded descriptor-relative reads rooted at the repository
- use no-follow atomic writes rooted at the worktree
- reject source and target symlink traversal
- cover traversal, source-symlink, and target-symlink regressions

### Resolved High: secure workspace primitive trusted caller normalization

`SecureWorkspaceFiles` used descriptor-relative operations but did not reject an
absolute or parent path itself. Existing callers normalized paths first, but the
low-level security contract was unsafe for direct or future use.

Resolution:

- validate every public read, write, and symlink-check path at the primitive
- reject absolute paths, empty file paths, `..`, NUL, and backslash syntax
- prove that rejected reads/writes cannot alter an outside file

## Architecture Assessment

Overall Clean Architecture score: **9.0/10**.

| Area | Score | Evidence |
| --- | ---: | --- |
| dependency direction | 9.5 | application is inward-only; interfaces do not select infra; graph is acyclic |
| domain isolation | 9.0 | deterministic policy is inward-owned; exactly two behavior-free import shims remain |
| use-case ownership | 9.0 | planning, workflow, verification, promotion, inbox, closeout, and task creation own effect order over ports |
| persistence and mapping | 9.0 | explicit mappers/codecs replace model-owned serialization and preserve legacy extension fields |
| external effects | 9.0 | Git, process, provider, filesystem, events, and verification are outer adapters with failure contracts |
| interface separation | 9.0 | CLI/MCP/inbox parse and render without direct infrastructure imports |
| testability and enforcement | 9.5 | architecture rules, adapter contracts, parity tests, security regressions, and installed-wheel smoke are executable |
| documentation | 9.5 | overview, data pipeline, runtime diagrams, ADR, and debt ledger name current implementation anchors |

The missing point is deliberate compatibility and migration cost, not a hidden
second implementation. The two repository shims, mutable legacy task-record
shape at several application ports, and compatibility patch points prevent a
fully typed, exception-free 10/10 boundary.

## Abstraction Review

### Appropriate abstractions

- Ports are concentrated around replaceable effects or nondeterminism: records,
  workspaces, providers, commands, evidence, events, Git, and pull requests.
- Codecs and repository mappers have one boundary responsibility and keep wire
  shapes out of models.
- Promotion execution, merged-PR recording, benchmark fixtures/rendering,
  spec-validation rules, and verification projection are split by independent
  change reason and test surface.
- Retained large modules each own one cohesive policy axis; line count alone was
  not used as a split criterion.

### Under-abstraction watch points

- `composition/evolution_evaluation.py` remains a large cross-context control
  coordinator. Its location prevents Evolution core from owning lifecycle
  authority, but task request, approval, freeze, materialization, and provider
  sequencing should become a dedicated Control application service when a real
  Hermes/GEPA transport replaces the compatibility patch points.
- `TaskRecord` is still a mutable mapping through compatibility-heavy workflow
  ports. Converting it fully to an aggregate requires a schema migration and
  installed-wheel compatibility window; doing it inside this refactor would
  create a second record authority.

### Over-abstraction watch points

- `TaskQueryService`, `AgentQueryService`, and `LifecycleApplicationService` are
  thin and mainly serve the bootstrap/public typed surface. They should not be
  copied as a general pattern; remove them when the bootstrap compatibility
  surface can be retired.
- Small composition modules are justified wiring functions. They contain no
  policy and are cheaper than allowing interfaces to choose concrete adapters.

## Logic And Bottleneck Review

- Canonical task updates serialize per record through file locks and atomic
  replacement. This is correct for a repository-local control plane; it is not a
  multi-host transaction model.
- General task listing remains linear in task count, while the daemon hot path
  uses the incremental workflow-candidate index. No current benchmark indicates
  a release-blocking scan bottleneck.
- Verification and Evolution commands execute sequentially by design to preserve
  evidence order, bounded output, timeout handling, and deterministic receipts.
- Compatibility facades resolve selected symbols at call time to preserve
  supported monkeypatch behavior. This adds indirection but avoids duplicate
  policy ownership.

## Behavioral Parity

The final local evidence after review fixes is:

| Gate | Result |
| --- | --- |
| lock consistency | `uv lock --check` passed |
| architecture/interface/hygiene target | 81 tests passed |
| persistence/path/inbox/lifecycle/spec/workflow target | 71 tests passed before the focused security additions |
| Python/MCP/Evolution target | 238 tests passed |
| final full suite | 735 tests passed |
| branch coverage | 85.2%, threshold 80% |
| standard build | sdist and wheel passed |
| offline build | cached sdist and wheel build passed |
| installed wheel | Python 3.14 import, CLI help, 25 MCP tools, and 32 MCP resources passed outside the source tree |
| diff integrity | `git diff --check` passed before review documentation |

The suite covers public import identity, CLI dispatch, MCP schemas/resources,
legacy mapping, unknown-field preservation, lifecycle gates, side-effect order,
path and symlink failures, timeout behavior, provider receipt integrity,
Evolution authority, and promotion receipts.

## Remaining Debt And Gates

The implementation debt ledger is authoritative. At this review point:

- no High or Medium implementation item remains
- exactly two import-only domain compatibility shims remain with explicit
  retirement conditions
- mutable-record and Evolution-coordinator watch points are future migration
  triggers, not additional authority exceptions
- independent review, Sisyphus verify, GitHub CI, PR merge, merge receipt, and
  merged-main revalidation remain release gates

The separate Sisyphus Harness work for Docker service separation, Hermes agent
evolution, GEPA, and a real 30.5B benchmark remains outside this repository task.
