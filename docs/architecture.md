# Sisyphus Architecture

This document describes the current architecture of Sisyphus as of 2026-04-14.

Sisyphus is a graph-native work system that runs inside a target Git repository and manages repository-local work state, task documents, worktrees, execution, verification, and closeout.

Its center is not an agent, a chat session, or a flat task list. The center is a controlled work world composed of specs, artifacts, typed relations, verification evidence, promotion state, invalidation state, and execution receipts. Intelligence is allowed to act on that world, but it is not allowed to become the authority over that world.

## Core Purpose

Sisyphus should be understood as:

> a graph-native work system centered on a controllable work world, with intelligence gradually internalized as operations over that world

This means:

- the authoritative state lives in durable, reviewable repository artifacts
- runtime intelligence is an operator over that state rather than the source of truth
- reconstructability matters as much as execution convenience

The current task runtime is still task-shaped, but the long-term architectural direction is artifact-centric.

## Hard State And Soft Cognition

The architecture separates two categories of system responsibility.

### Hard State

Hard state is the durable truth the system must be able to recover, validate, diff, and promote.

- spec artifacts
- produced artifacts
- typed edges and slot bindings
- verification claims and evidence
- promotion decisions
- invalidation state
- execution receipts

### Soft Cognition

Soft cognition improves throughput and adaptability, but it must not replace durable state.

- planning
- decomposition
- scheduling
- impact analysis
- retry and recovery strategy
- replanning
- semantic review
- context condensation

The governing rule is:

> intelligence may be internalized, but it must not overwrite or bypass hard-state authority

## Task And Artifact Model

Tasks are still first-class, but they are not the primary durable object. Artifacts carry durable state. Tasks are operators that produce, transform, or compose artifacts.

The intended model is:

- `TaskSpec`: the planned operation
- `TaskRun`: the executed operation and its receipt
- `Artifact`: a durable state object
- `CompositeArtifact`: a higher-order artifact whose validity depends on typed relationships among child artifacts
- `VerificationArtifact`: evidence for a specific claim
- `PromotionDecision`: the recorded decision that an artifact obligation is closed

This implies two important boundaries:

- `TaskSpec` and `TaskRun` must remain distinct
- higher-order results are not loose bundles; they are contract-bearing composite objects

## Composite Artifacts And Reconstruction

A higher-order artifact exists only when the system can recover:

- which child artifacts participated
- which task specs and task runs produced them
- which typed edges and slot bindings connected them
- which composition rule made the result valid
- which verification claims supported the result
- which promotion state the result currently holds

For that reason, a final artifact should be understood as having two layers:

- `payload`: the usable result
- `envelope`: the reconstructable composition record explaining why the result is valid

This reconstructability requirement is stronger than simple lineage tracking. It is a design constraint for persistence, verification, invalidation, and promotion.

## Verification, Promotion, And Invalidation

Verification is not a generic boolean. It is proof for a claim over a scope with explicit dependencies and evidence.

The system should reason about verification in three layers:

- `local`: an artifact is internally valid
- `cross`: relationships between artifacts are valid
- `composite`: a higher-order artifact satisfies its intended obligation

Higher-layer verification is not implied by lower-layer verification.

Promotion is likewise not task completion. Promotion is obligation closure for an artifact. A promoted artifact should have:

- required slots filled
- invariants satisfied
- required verification claims passed
- no stale dependencies
- no unresolved conflicts
- required approvals or evidence recorded

Invalidation must precede operational change requests. When an input changes, the system first computes which composites or verification claims are stale, and only then decides whether to reverify, reassemble, replan, or issue a new change request.

## Authority Boundary For Intelligence

Hermes-like agent runtimes remain useful, but they must stay outside the authoritative state boundary.

Those runtimes usually carry hidden state through:

- session accumulation
- memory injection
- summarization or compression
- fallback and retry policy
- autonomous loop decisions

That is useful for general-purpose agent behavior, but it introduces drift if treated as the runtime authority.

The architectural rule is therefore:

- Sisyphus owns the authoritative runtime contract
- external or embedded agent intelligence remains an optional cognition module
- hard-state persistence, receipts, verification, promotion, and invalidation stay inside Sisyphus

## Next Design Lock

The most productive next step is not a universal composition engine. It is a concrete protocol for one representative composite artifact type.

That design pass should lock:

1. the artifact type and its named or collection slots
2. the key invariants across those slots
3. the verification obligations at `local`, `cross`, and `composite` layers
4. the promotion gate
5. the invalidation matrix for changed inputs
6. the reconstruction envelope fields

Once one representative protocol is fixed, common composition kernels and reusable graph machinery can be extracted from it.

### Recommended First Protocol

The best first protocol to lock is a repository-change composite for feature delivery.

The concrete definition now lives in [docs/feature-change-artifact.md](./feature-change-artifact.md).

One practical shape is:

- `FeatureChangeArtifact`
  - `spec` slot
  - `implementation_candidates[]` collection slot
  - `selected_implementation` slot
  - `tests[]` collection slot
  - `verification_claims[]` collection slot
  - optional `approvals[]` collection slot

This is the right first candidate because it matches the repository's current workflow shape while still forcing the system to define:

- role-based slots and collection slots
- cross-artifact invariants such as spec or implementation compatibility
- layered verification from local checks to composite acceptance
- promotion rules for when a change is actually ready
- invalidation behavior when spec, implementation, or tests move independently
- a reconstructable envelope that can later map to branch, PR, and merge decisions

## System Shape

At a high level, the current implementation is organized as a layered orchestration stack:

```text
+------------------------------------------------------------------+
| Layer 1. Interfaces                                               |
| CLI commands, Python API, Discord bot, MCP clients                |
| src/sisyphus/cli.py, api.py, discord_bot.py                       |
+------------------------------------------------------------------+
| Layer 2. Intake and Service Loop                                  |
| Conversation queue, inbox processing, daemon/service loop         |
| src/sisyphus/daemon.py, service.py                                |
+------------------------------------------------------------------+
| Layer 3. Workflow and Policy                                      |
| Workflow transitions, plan/spec gates, subtask generation         |
| src/sisyphus/workflow.py, planning.py                             |
+------------------------------------------------------------------+
| Layer 4. Execution Adapters                                       |
| Provider wrappers, prompt assembly, tracked agent runtime         |
| src/sisyphus/provider_wrapper.py, codex_prompt.py, agent_runtime.py |
+------------------------------------------------------------------+
| Layer 5. Persistence and Workspace                                |
| Task JSON, agent JSON, task docs, templates, git worktrees        |
| src/sisyphus/state.py, agents.py, templates.py, gitops.py         |
+------------------------------------------------------------------+
| Layer 6. Verification and Closeout                                |
| Strategy extraction, audits, verify commands, close gates         |
| src/sisyphus/strategy.py, audit.py, closeout.py                   |
+------------------------------------------------------------------+
| Layer 7. Core Integration Services                                |
| Event bus, MCP core service, shared adapter logic                 |
| src/sisyphus/bus.py, bus_jsonl.py, events.py, mcp_core.py         |
+------------------------------------------------------------------+
| Layer 8. MCP Gateway                                              |
| Official MCP SDK stdio gateway, tool/resource binding             |
| src/sisyphus/mcp_server.py                                        |
+------------------------------------------------------------------+
```

## Layer Diagram

The main dependency flow is downward. Upper layers coordinate lower layers and should not contain low-level persistence details unless needed for orchestration.

```mermaid
flowchart TD
    A[Interfaces\nCLI / API / Discord Bot]
    B[Intake and Service Loop\nqueue / daemon / service]
    C[Workflow and Policy\nworkflow / planning]
    D[Execution Adapters\nprovider wrapper / prompt / agent runtime]
    E[Persistence and Workspace\nstate / agents / templates / gitops]
    F[Verification and Closeout\nstrategy / audit / closeout]

    A --> B
    A --> C
    B --> C
    B --> E
    C --> D
    C --> E
    C --> F
    D --> E
    F --> E
    G[Core Integration Services\nbus / events / MCP core]
    H[MCP Gateway\nMCP SDK stdio transport]
    B --> G
    C --> G
    F --> G
    H --> G
```

## MCP Boundary

MCP is the shared product interface for Codex, Claude, and any future agent client. To keep that interface stable while the orchestration core evolves, the codebase now treats MCP as a thin gateway over a repo-local core service.

```mermaid
flowchart LR
    A[Codex / Claude / Other Client]
    B[MCP Gateway\nmcp_server.py]
    C[MCP Core Service\nmcp_core.py]
    D[Sisyphus Core\nworkflow / planning / audit / closeout]
    E[State + Docs + Agents]
    F[Event Bus]

    A --> B
    B --> C
    C --> D
    C --> E
    D --> F
    C --> F
```

The intended responsibilities are:

- `mcp_server.py`: official MCP Python SDK server, stdio transport, tool/resource binding.
- `mcp_core.py`: repo-aware tool/resource resolution and response shaping.
- `bus.py` and related modules: publication surface for visualization, monitoring, and other apps.
- sisyphus core modules: workflow, conformance, verification, and persistence policy.

## Evolution Control Plane

The repository now also contains a separate read-only evolution control plane in [`src/sisyphus/evolution/`](../src/sisyphus/evolution/). This subsystem is intentionally adjacent to the live orchestration workflow rather than embedded inside it.

The current implemented slices are:

- target registry and run planning in `targets.py` and `runner.py`
- stage and failure contracts in `stages.py`
- artifact-cycle and handoff contracts in `artifacts.py` and `handoff.py`
- dataset extraction from task records, conformance state, verify metadata, and event logs in `dataset.py`
- baseline/candidate harness planning and evaluation-only execution in `harness.py`
- hard-guard evaluation and weighted scoring in `constraints.py` and `fitness.py`
- stable reporting projection in `report.py`
- read-only orchestration and append-only run persistence in `orchestrator.py`

The following pieces are still future work:

- candidate materialization and full worktree-backed harness execution
- follow-up task handoff into the Sisyphus lifecycle
- MCP evolution tools/resources
- promotion and invalidation envelopes backed by receipts

### Evolution Authority Boundary

The control-plane boundary is strict:

- evolution owns planning, candidate comparison, guard evaluation, fitness scoring, and report generation
- evolution may write append-only run artifacts under `.planning/evolution/runs/<run_id>/`
- evolution must not mutate live repository state, live task state, approval state, or promotion state
- Sisyphus owns task creation, plan review, spec freeze, provider execution, verification, receipts, promotion, and invalidation

In practical terms, an evolution run may recommend or request a follow-up task, but it may not approve, freeze, verify, or promote its own result.

### Evolution System Diagram

```mermaid
flowchart LR
    subgraph Runtime["Runtime orchestration plane"]
        Clients[CLI / API / MCP clients]
        MCP[MCP gateway and core]
        Workflow[Workflow / planning / verify / closeout]
        RepoState[Task records / task docs / conformance / event bus]

        Clients --> MCP
        Clients --> Workflow
        MCP --> Workflow
        Workflow --> RepoState
        MCP --> RepoState
    end

    subgraph Evolution["Evolution control plane"]
        Targets[Target registry]
        Run[Run planner]
        Stages[Stage contracts]
        Artifacts[Artifact and handoff contracts]
        Dataset[Dataset builder]
        Harness[Harness planner]
        Guards[Constraints]
        Fitness[Fitness scorer]
        Report[Report model]
        Orchestrator[Read-only orchestrator]

        Targets --> Run
        Run --> Stages
        Run --> Artifacts
        Run --> Dataset
        Dataset --> Harness
        Harness --> Guards
        Harness --> Fitness
        Guards --> Report
        Fitness --> Report
        Report --> Orchestrator
    end

    RepoState --> Dataset
    Report -. future follow-up request .-> Workflow
    MCP -. future evolution MCP surface .-> Report
```

### Evolution Evaluation Loop

```mermaid
flowchart TD
    A[Select evolution targets] --> B[Plan evolution run]
    B --> C[Build dataset from task records, verify traces, conformance, and events]
    C --> D[Plan baseline and candidate harness evaluations]
    D --> E[Populate comparable metrics]
    E --> F[Evaluate hard guards]
    E --> G[Compute weighted fitness]
    F --> H[Build reviewable report]
    G --> H
    H --> I[Append-only run artifacts]
    I --> J[Future follow-up request or MCP projection]
```

Today this loop is implemented as a planning and evaluation model layer through the read-only orchestrator plus evaluation-only harness execution helpers. It does not yet execute candidate mutations, materialize branch-backed candidates, or land approved results through the normal Sisyphus lifecycle.

## Class Diagram

The following diagram shows the main runtime objects and persistent artifacts, with emphasis on where data is stored and how it moves between modules.

```mermaid
classDiagram
    class CLI {
        +build_parser()
        +handle_request()
        +handle_verify()
        +handle_close()
    }

    class API {
        +queue_conversation()
        +request_task()
        +run_until_stable()
    }

    class Daemon {
        +queue_conversation_event()
        +process_inbox_event()
        +run_daemon()
    }

    class Workflow {
        +run_workflow_cycle()
        +_advance_task()
        +_run_subtask()
    }

    class Planning {
        +enforce_plan_approved()
        +freeze_task_spec()
        +generate_subtasks()
    }

    class ProviderWrapper {
        +run_provider_wrapper()
        +_build_default_launch()
    }

    class Audit {
        +run_verify()
        +_run_verify_commands()
    }

    class Closeout {
        +run_close()
    }

    class State {
        +build_task_record()
        +load_task_record()
        +save_task_record()
        +sync_task_support_files()
    }

    class Agents {
        +register_agent()
        +update_agent()
        +list_agents()
    }

    class GitOps {
        +create_task_branch_and_worktree()
        +remove_task_branch_and_worktree()
    }

    class Strategy {
        +sync_test_strategy_from_docs()
    }

    class TaskRecord {
        +id
        +type
        +slug
        +status
        +stage
        +workflow_phase
        +plan_status
        +spec_status
        +verify_status
        +subtasks
        +gates
        +meta
    }

    class ConversationEvent {
        +id
        +event_type
        +status
        +payload
        +result
        +error
    }

    class AgentRecord {
        +agent_id
        +parent_task_id
        +role
        +provider
        +status
        +last_heartbeat_at
        +error
    }

    class TaskDocs {
        +BRIEF.md
        +PLAN.md or FIX_PLAN.md
        +REPRO.md
        +VERIFY.md
        +LOG.md
    }

    class Worktree {
        +branch
        +path
    }

    CLI --> API : invokes
    CLI --> Daemon : invokes
    API --> Daemon : queues/processes
    API --> Workflow : runs until stable
    Daemon --> ConversationEvent : reads/writes
    Daemon --> State : loads/saves task
    Daemon --> GitOps : provisions workspace
    Daemon --> Planning : enforces gates
    Daemon --> ProviderWrapper : launches provider
    Workflow --> State : reads/writes task
    Workflow --> Planning : advances policy state
    Workflow --> ProviderWrapper : launches subtask agent
    Workflow --> Audit : verifies
    Workflow --> Closeout : closes
    Audit --> Strategy : derives test strategy
    Audit --> State : reads/writes task
    Closeout --> State : reads/writes task
    State --> TaskRecord : persists
    State --> TaskDocs : syncs
    Agents --> AgentRecord : persists
    GitOps --> Worktree : creates/removes
    TaskRecord --> TaskDocs : references
    TaskRecord --> Worktree : references
```

## Core Responsibilities

### 1. Interfaces

The interface layer exposes the system to operators and automation.

- `cli.py` defines command entrypoints such as `request`, `ingest`, `daemon`, `serve`, `verify`, `close`, `plan`, `spec`, and `agents`.
- `api.py` provides a library-facing wrapper around queueing, processing, and running the workflow until stable.
- `discord_bot.py` is an optional external integration path that feeds the same orchestration model.

This layer should stay thin. It is mostly argument parsing, command dispatch, and result presentation.

### 2. Intake and Service Loop

This layer converts a user request into repository-local events and drives the orchestration loop.

- `daemon.py` serializes conversation requests into inbox event JSON files.
- The daemon processes pending events, creates tasks, and moves events into processed or failed inbox folders.
- `service.py` wraps the daemon loop and can emit task notifications based on state changes.

This is the operational backbone of the system. It separates request intake from workflow advancement.

### 3. Workflow and Policy

This layer contains the orchestration rules for task progression.

- `workflow.py` advances tasks through plan approval, spec freeze, subtask generation, subtask execution, verification, and closeout.
- `planning.py` defines plan and spec status rules, plan review rounds, and blocking gates.

This layer acts as the state machine, even though it is implemented as direct field transitions rather than a formal state machine framework.

### 4. Execution Adapters

This layer is the boundary between Sisyphus and external coding agents.

- `provider_wrapper.py` normalizes launch modes and constructs the default provider command.
- `codex_prompt.py` builds the prompt for Codex execution in the task worktree.
- `agent_runtime.py` runs tracked agents and updates their lifecycle state.
- `wrappers/codex/run.py` and `wrappers/claude/run.py` are small provider launch shims.

This layer is intentionally adapter-shaped. The orchestration logic does not need to know the full mechanics of each provider.

### 5. Persistence and Workspace

This layer stores state and provisions task workspaces.

- `state.py` defines the task record shape and persists task JSON.
- `agents.py` tracks per-agent lifecycle as JSON files with heartbeat-based status derivation.
- `templates.py` materializes task document templates into the task directory.
- `gitops.py` creates and removes task branches and worktrees.
- `creation.py` combines task record creation, worktree setup, and rollback behavior.

This is a file-first architecture. The source of truth is repository-local state, not an external database.

### Task Worktree Baseline Rule

Task worktrees are provisioned from the configured `base_branch`, not from the current root worktree's dirty state.

- `creation.py` calls `gitops.create_task_branch_and_worktree()`.
- `gitops.create_task_branch_and_worktree()` runs `git worktree add -b <branch> <target> <base_ref>`.
- `base_ref` is resolved from `config.base_branch` by `gitops.resolve_base_ref()`.

That means an in-progress root worktree migration or refactor is not automatically present in a newly created task worktree. The only supported escape hatch is direct-change adoption:

- `daemon.py` can apply `adopt_current_changes` during task creation.
- adoption copies the current root dirty paths into the new task worktree and records the overlay in `task.json -> meta.adopted_changes`.

Operationally, when the root worktree becomes the authoritative source of truth, ongoing implementation should move to a freshly adopted task baseline. Older task worktrees should be treated as stale references until their scope is replayed or the tasks are closed.

### 6. Verification and Closeout

This layer converts planning intent into executable or inspectable evidence.

- `strategy.py` parses structured testing and review intent out of `PLAN.md` or `FIX_PLAN.md`.
- `audit.py` evaluates documentation completeness, strategy completeness, plan gates, and configured verify commands.
- `closeout.py` enforces final gates such as verify completion and worktree cleanliness.

This layer is policy-heavy. It is where the system translates "is this done?" into explicit checks.

### 7. Integration Adapters

This layer exposes Sisyphus to external consumers without moving the source of truth out of repository-local state.

- `events.py` defines a domain-event envelope.
- `bus.py` defines a pluggable publisher interface.
- `bus_jsonl.py` provides a default JSONL publisher.
- `mcp_adapter.py` exposes MCP-friendly tool and resource operations without coupling the core to a specific MCP server implementation.
- `mcp_server.py` binds those operations to the official MCP Python SDK stdio server entrypoint.

This layer is intentionally replaceable. It is where web apps, bots, and MCP servers attach.

The default MCP server entrypoint is:

```bash
sisyphus-mcp
```

By default it targets the current repository. To point it at a different repository root, set:

```bash
export SISYPHUS_REPO_ROOT=/path/to/repo
```

## Primary Runtime Flows

### Request to Task

```text
Operator/API request
-> queue conversation event
-> daemon processes inbox event
-> create task workspace and task docs
-> apply initial gates
-> optionally auto-run worker/provider
-> run workflow until stable
```

Relevant modules:

- `api.py`
- `daemon.py`
- `creation.py`
- `planning.py`
- `provider_wrapper.py`
- `workflow.py`

### Workflow Progression

```text
Task exists
-> plan approved?
-> spec frozen?
-> subtasks generated?
-> queued subtask run
-> all subtasks complete
-> verify
-> close
```

If any blocking gate appears, the task moves to a blocked or `needs_user_input` state instead of continuing automatically.

### Verify and Close

```text
Sync test strategy from task docs
-> collect doc/spec/plan gates
-> run configured verify commands
-> write VERIFY.md
-> if no gates, allow close
-> if clean enough and verified, mark task closed
```

## Sequence Diagram

The sequence below focuses on data transfer. It shows where payloads become events, where events become task records, where task records become provider input, and where execution results flow back into persistent state.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as CLI/API
    participant Daemon as daemon.py
    participant Inbox as .planning/inbox/*.json
    participant Creation as creation.py + gitops.py
    participant TaskDir as .planning/tasks/<task-id>/
    participant State as state.py
    participant Planning as planning.py
    participant Provider as provider_wrapper.py
    participant Agent as Codex or Claude
    participant Workflow as workflow.py
    participant Strategy as strategy.py
    participant Audit as audit.py
    participant Closeout as closeout.py

    User->>CLI: request("Add an agent dashboard")
    CLI->>Daemon: queue_conversation_event(message, title, task_type, provider, auto_run)
    Daemon->>Inbox: write pending event JSON
    CLI->>Daemon: process_inbox_event(event_path)
    Daemon->>Inbox: read event JSON
    Daemon->>Creation: create_task_workspace(task_type, slug)
    Creation->>Creation: create branch + git worktree
    Creation->>TaskDir: create task directory
    Creation->>TaskDir: materialize BRIEF/PLAN/VERIFY/LOG templates
    Creation->>State: save initial task.json
    Daemon->>TaskDir: write BRIEF.md and PLAN.md or REPRO.md/FIX_PLAN.md
    Daemon->>State: load task.json
    Daemon->>State: update meta.source_event_id, default_provider, source_context
    State->>TaskDir: sync task.json and docs into worktree copy
    Daemon->>Planning: enforce_plan_approved(action=auto-run)
    Planning->>State: read/update task.json gates and status
    Daemon->>Planning: enforce_spec_frozen(action=auto-run)
    Planning->>State: read/update task.json gates and status

    alt auto-run allowed
        Daemon->>Provider: run_provider_wrapper(task_id, agent_id, role, instruction)
        Provider->>State: load task context for prompt
        Provider->>Agent: send prompt via stdin and run command
        Agent-->>Provider: final message and exit code
        Provider->>State: update agent/task metadata
    else blocked by plan or spec gate
        Daemon->>State: persist blocked status and gates
    end

    CLI->>Workflow: run_until_stable()
    loop while progress exists
        Workflow->>State: load task.json
        Workflow->>Planning: inspect plan/spec status
        alt subtasks missing
            Workflow->>State: write generated subtasks to task.json
        else queued subtask exists
            Workflow->>Provider: run subtask agent
            Provider->>Agent: execute in task worktree
            Agent-->>Provider: exit code and last message
            Provider->>State: update agent/task metadata
            Workflow->>State: mark subtask completed or failed
        else all subtasks completed
            Workflow->>Audit: run_verify(task_id)
            Audit->>State: load task.json
            Audit->>Strategy: parse PLAN.md or FIX_PLAN.md
            Strategy-->>Audit: test_strategy data
            Audit->>TaskDir: read task docs
            Audit->>TaskDir: run verify commands in task dir
            Audit->>TaskDir: write VERIFY.md
            Audit->>State: persist verify_status, gates, results
            alt verify passed
                Workflow->>Closeout: run_close(task_id)
                Closeout->>TaskDir: inspect git status
                Closeout->>State: persist closed status or close gates
            else verify blocked
                Workflow->>State: persist needs_user_input
            end
        end
    end
```

## Data Transport Notes

The main data handoff points are:

- request payload to inbox event JSON
- inbox event JSON to `task.json` plus task docs
- `task.json` plus task docs to provider prompt input
- provider result to agent record and subtask status
- task docs to parsed `test_strategy`
- verify command results to `VERIFY.md` and `task.json`
- task and conformance changes to domain events on the event bus
- repository-local state and task docs to MCP tool/resource responses

The most important persistent channels are:

- `.planning/inbox/pending`, `.planning/inbox/processed`, `.planning/inbox/failed`
- `.planning/tasks/<task-id>/task.json`
- `.planning/tasks/<task-id>/*.md`
- `.planning/tasks/<task-id>/agents/*.json`
- task worktree copies synced from the main task directory

## Data Model

The central record is `task.json`. Important fields include:

- identity: `id`, `type`, `slug`
- execution state: `status`, `stage`, `workflow_phase`
- review state: `plan_status`, `spec_status`, `plan_review_round`
- workspace state: `task_dir`, `worktree_path`, `branch`, `base_branch`
- verification state: `verify_profile`, `verify_commands`, `verify_status`, `audit_attempts`
- policy state: `gates`, `test_strategy`, `subtasks`
- metadata: `meta`

Supporting artifacts live next to `task.json`:

- `BRIEF.md`
- `PLAN.md` or `FIX_PLAN.md`
- `REPRO.md` for issue tasks
- `VERIFY.md`
- `LOG.md`
- `agents/*.json`

## Architectural Characteristics

### Strengths

- Repository-local state makes tasks easy to inspect, diff, back up, and reason about.
- Git worktrees provide strong isolation per task without needing a separate orchestration service.
- The system leaves durable artifacts for planning, execution, and verification.
- Provider integration is adapter-based, so orchestration is not hard-coded to a single agent runtime.

### Tradeoffs

- State transitions are distributed across modules through shared string fields in `task.json`.
- Document parsing is format-sensitive. If plan templates drift, strategy extraction can degrade.
- File-based event processing is simple and inspectable, but not designed for high-concurrency distributed workloads.
- Verification policy is powerful, but tightly coupled to the task document conventions.

## Boundary Guidelines

The current architecture works best when module responsibilities stay disciplined:

- `cli.py` and `api.py` should remain thin entry layers.
- `daemon.py` should own queue processing and event lifecycle, not detailed business policy.
- `workflow.py` should coordinate transitions, not absorb template parsing or low-level git logic.
- `planning.py`, `audit.py`, and `closeout.py` should remain policy modules.
- `state.py`, `agents.py`, and `gitops.py` should remain infrastructure modules.
- provider-specific behavior should stay behind `provider_wrapper.py` and wrapper entrypoints.

## Suggested Future Refactoring Directions

These are not required for the current design, but they are the most likely pressure points as the project grows:

- Introduce a more explicit task state transition model to reduce string-based implicit rules.
- Separate verification policy from verify command execution more cleanly.
- Add stronger schema validation for `task.json` and agent records.
- Make task document parsing more resilient or move structured strategy data into a dedicated machine-readable file.
- Isolate follow-up task logic and auto-loop policy from core daemon intake for simpler testing.

## Summary

Sisyphus is best understood as a repository-local orchestration kernel for AI-assisted task execution.

Its architecture is centered on:

- file-based state
- git worktree provisioning
- policy-driven workflow transitions
- adapter-based agent execution
- evidence-oriented verification and closeout

That makes it pragmatic, inspectable, and easy to operate in a single repository context, with the main long-term risk being the growing complexity of implicit state transitions and document-driven policy parsing.
