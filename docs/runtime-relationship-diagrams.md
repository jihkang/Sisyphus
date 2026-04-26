# Sisyphus Runtime Relationship Diagrams

This document complements [architecture.md](./architecture.md) with diagrams that make runtime boundaries explicit.

The main ambiguity to avoid is treating agent execution, task records, artifact projections, and repository promotion as one layer. They are related, but they have different authority.

The diagrams below split:

1. current runtime authority
2. artifact-governed feature-change path
3. target artifact authority
4. main and evolution loop
5. turn-to-contract materialization
6. artifact state machine
7. adapter contract boundary

## 1. Current Runtime Authority

The operator-facing control surface is still task-shaped. Feature work now also materializes artifact snapshots and compiled obligations.

```mermaid
flowchart LR
    subgraph Request["Request Surface"]
        User[User request]
        CLI[CLI / API / MCP / Discord]
    end

    subgraph TaskRuntime["Task Runtime Authority"]
        TaskState[task.json]
        TaskDocs[BRIEF / PLAN / VERIFY / LOG]
        Worktree[task branch and worktree]
        Agents[agent records]
        Verify[verify receipts]
        Events[event log]
    end

    subgraph ArtifactRuntime["Artifact-Governed Runtime"]
        Projection[FeatureChangeArtifact projection]
        Snapshot[persisted projection snapshot]
        Evaluation[FeatureChange evaluation]
        Intents[ObligationIntent records]
        Queue[CompiledObligation queue]
        Receipts[obligation execution receipts]
    end

    subgraph Promotion["Promotion Boundary"]
        ArtifactDecision[ArtifactPromotionDecision]
        RepoExecution[RepositoryPromotionExecution]
        MergeReceipt[merge receipt and changeset]
    end

    User --> CLI
    CLI --> TaskState
    CLI --> TaskDocs
    CLI --> Worktree
    TaskState --> Projection
    TaskDocs --> Projection
    Verify --> Projection
    Projection --> Snapshot
    Projection --> Evaluation
    Snapshot --> Evaluation
    Evaluation --> Intents
    Intents --> Queue
    Queue --> Receipts
    Receipts --> Verify
    Evaluation --> ArtifactDecision
    ArtifactDecision --> RepoExecution
    RepoExecution --> MergeReceipt
    MergeReceipt --> TaskState
```

## 2. Feature-Change Obligation Path

The DSL defines meaning. Execution policy defines how an obligation is run.

```mermaid
flowchart TD
    A[Feature task record and docs]
    B[project_feature_task_record]
    C[FeatureChangeArtifact projection]
    D[persist artifacts/projection/feature-change.json]
    E[evaluate_feature_task_projection]
    F[ObligationIntent]
    G[ProtocolSpec + ObligationSpec + InputContract]
    H[compile_feature_change_obligations]
    I[CompiledObligation]
    J[MaterializedInputSet fingerprint]
    K[persist artifacts/obligations/compiled.json]
    L[ExecutionPolicy]
    M[execute_next_feature_change_obligation]
    N[verification or blocked receipt]
    O[refresh projection snapshot]

    A --> B
    B --> C
    C --> D
    C --> E
    D --> E
    E --> F
    F --> H
    G --> H
    H --> I
    I --> J
    I --> K
    J --> K
    K --> M
    L --> M
    M --> N
    N --> O
    O --> D
```

The important invariant is that a compiled obligation is keyed by its materialized input fingerprint. A changed input creates a new obligation instance rather than silently changing the meaning of an old verdict.

## 3. Target Artifact Authority

The intended long-term center is a typed artifact graph. Tasks remain operators, but they should not be the only durable source of truth.

```mermaid
flowchart LR
    subgraph Runtime["Deterministic Runtime Operations"]
        Intake[intake]
        Execute[execute]
        Verify[verify]
        Promote[promote]
        Invalidate[invalidate]
    end

    subgraph Graph["Typed Artifact Graph"]
        Specs[TaskSpec]
        Runs[TaskRun]
        Artifacts[ArtifactRecord]
        Composite[CompositeArtifactRecord]
        Claims[VerificationClaimRecord]
        Decisions[ArtifactPromotionDecision]
        Edges[typed edges and slot bindings]
    end

    subgraph Policy["Replaceable Execution Policy"]
        Agent[agent/provider selection]
        Tool[tool runner]
        Budget[budget / retry / timeout]
    end

    Intake --> Specs
    Execute --> Runs
    Execute --> Artifacts
    Verify --> Claims
    Promote --> Decisions
    Invalidate --> Edges

    Specs --> Composite
    Artifacts --> Composite
    Claims --> Composite
    Edges --> Composite

    Policy -. configures execution .-> Execute
    Policy -. does not define artifact meaning .-> Graph
```

## 4. Main And Evolution Loop

The main runtime is live and authoritative. Evolution is adjacent: it can read, evaluate, and request follow-up work, but it must route changes through Sisyphus lifecycle gates.

```mermaid
flowchart LR
    subgraph Main["Main Runtime"]
        Requests[operator requests]
        TaskLoop[workflow / daemon loop]
        TaskState[task records and docs]
        ArtifactState[artifact snapshots and obligations]
        Promotion[promotion receipts]
    end

    subgraph Evolution["Evolution Control Plane"]
        Dataset[dataset extraction]
        Harness[harness evaluation]
        Fitness[constraints and fitness]
        Report[reviewable report]
        Followup[follow-up request bridge]
    end

    subgraph Gates["Sisyphus Gates"]
        Plan[plan approval]
        Spec[spec freeze]
        Verify[verification]
        Close[close / promotion]
    end

    Requests --> TaskLoop
    TaskLoop --> TaskState
    TaskLoop --> ArtifactState
    TaskLoop --> Promotion

    TaskState --> Dataset
    ArtifactState --> Dataset
    Promotion --> Dataset
    Dataset --> Harness
    Harness --> Fitness
    Fitness --> Report
    Report --> Followup

    Followup --> Plan
    Plan --> Spec
    Spec --> Verify
    Verify --> Close
    Close --> TaskLoop
```

## 5. Turn-To-Contract Materialization

Agent reasoning may be stochastic. The persisted contract must be deterministic enough to replay.

```mermaid
flowchart TD
    Input[user input and repository state]
    Retrieval[retrieval and context selection]
    Agent[agent reasoning]
    Slots[structured slots]
    Contract[contractual fields]
    Info[informational fields]
    Persist[repo-local persistence]
    Projection[artifact projection]
    Queue[obligation queue]

    Input --> Retrieval
    Retrieval --> Agent
    Input --> Agent
    Agent --> Slots
    Slots --> Contract
    Slots --> Info
    Contract --> Persist
    Info --> Persist
    Persist --> Projection
    Projection --> Queue
```

Contractual fields are the governance boundary. Informational fields can help retrieval and review, but they must not weaken deterministic replay of the contract.

## 6. Artifact State Machine

The feature-change evaluator currently derives states through `promotable`. Repository merge and merge receipt recording are handled by the separate repository promotion execution path.

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> candidate: required starting slots exist
    candidate --> verified: required claims pass
    verified --> promotable: freshness, invariants, approvals
    promotable --> promoted: repository promotion recorded

    draft --> invalid: malformed contract
    candidate --> invalid: invariant or claim failure
    verified --> invalid: invariant or claim failure
    promotable --> invalid: broken obligation

    verified --> stale: dependency changed
    promotable --> stale: dependency changed
    stale --> candidate: recompose
    stale --> verified: reverify
    invalid --> candidate: repair inputs
```

## 7. Adapter Contract Boundary

External agents should connect through a narrow adapter contract rather than owning Sisyphus state directly.

```mermaid
flowchart LR
    subgraph External["External Runtime"]
        Codex[Codex]
        Claude[Claude]
        Other[other agent/tool]
    end

    subgraph Adapter["Adapter Layer"]
        Prompt[prompt and input materialization]
        ToolRunner[tool/provider runner]
        ReceiptWriter[receipt writer]
    end

    subgraph Contract["Deterministic Contract Boundary"]
        InputContract[InputContract]
        MaterializedInputs[MaterializedInputSet]
        ProducedArtifacts[produced artifacts / claims]
        Receipts[execution receipts]
    end

    subgraph Runtime["Sisyphus Runtime"]
        TaskRuntime[task runtime]
        ArtifactRuntime[artifact projection and queue]
        Gates[verification and promotion gates]
    end

    Codex --> Prompt
    Claude --> Prompt
    Other --> ToolRunner
    Prompt --> InputContract
    ToolRunner --> MaterializedInputs
    ToolRunner --> ProducedArtifacts
    ReceiptWriter --> Receipts
    InputContract --> ArtifactRuntime
    MaterializedInputs --> ArtifactRuntime
    ProducedArtifacts --> ArtifactRuntime
    Receipts --> Gates
    TaskRuntime --> ArtifactRuntime
    Gates --> TaskRuntime
```

The adapter may vary by agent or provider. The contract boundary may not.
