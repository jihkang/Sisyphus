# Sisyphus Runtime Relationship Diagrams

This document complements [architecture.md](./architecture.md) with diagrams that separate the two concerns that are easy to conflate in prose:

- the current authoritative runtime vs the long-term artifact-centric target
- static authority boundaries vs dynamic time-based evolution flow

The diagrams below therefore split:

1. current runtime authority
2. target runtime authority
3. daily main/evolution loop
4. turn-to-arc materialization
5. artifact state machine
6. adapter contract boundary

## 1. Current Authority Map

This is the current implementation shape. The authoritative runtime is still task-shaped.

```mermaid
flowchart LR
    subgraph Main["Main Runtime"]
        User[User request]
        MainLoop[Task orchestration loop]
    end

    subgraph Authority["Authoritative repo-local runtime"]
        TaskState[task.json]
        TaskDocs[task docs]
        Receipts[verify receipts]
        Agents[agent records]
        Events[event log]
    end

    subgraph Derived["Derived artifact surfaces"]
        Projection[feature-task projection]
        Eval[promotion and invalidation evaluator]
    end

    subgraph Evo["Evolution Runtime"]
        EvoBatch[evolution batch and scoring]
        EvoStore[append-only evolution run artifacts]
    end

    subgraph Gate["Normal Sisyphus gates"]
        PlanGate[plan approve]
        SpecGate[spec freeze]
        VerifyGate[verify]
        PromoteGate[promotion and closeout]
    end

    User --> MainLoop
    MainLoop -->|read/write| TaskState
    MainLoop -->|read/write| TaskDocs
    MainLoop -->|read/write| Receipts
    MainLoop -->|read/write| Agents
    MainLoop -->|read/write| Events

    TaskState --> Projection
    TaskDocs --> Projection
    Receipts --> Projection
    Projection --> Eval

    EvoBatch -. read live authority .-> TaskState
    EvoBatch -. read live authority .-> TaskDocs
    EvoBatch -. read live authority .-> Receipts
    EvoBatch -. read live authority .-> Events
    EvoBatch -->|append-only| EvoStore

    EvoBatch -->|request follow-up only| PlanGate
    PlanGate --> SpecGate
    SpecGate --> VerifyGate
    VerifyGate --> PromoteGate
    PromoteGate -->|authoritative updates| TaskState
    PromoteGate -->|authoritative updates| TaskDocs
    PromoteGate -->|authoritative updates| Receipts
```

## 2. Target Authority Map

This is the intended direction. The center becomes a typed artifact graph rather than task records alone.

```mermaid
flowchart LR
    subgraph Main["Main Runtime"]
        MainOps[deterministic runtime operations]
    end

    subgraph Graph["Typed artifact graph"]
        Specs[TaskSpec]
        Runs[TaskRun]
        Artifacts[Artifact and CompositeArtifact]
        Claims[VerificationArtifact]
        Decisions[PromotionDecision]
        Similarity[reference and similarity edges]
    end

    subgraph Info["Informational fields"]
        Summary[summary and retrieval hints]
    end

    subgraph Evo["Evolution Runtime"]
        EvoRead[evolution analysis and selection]
        EvoBatchStore[append-only evolution artifacts]
    end

    subgraph Gate["Main-runtime handoff gate"]
        Handoff[spec freeze and review-gated handoff]
    end

    MainOps -->|read/write contractual state| Specs
    MainOps -->|read/write contractual state| Runs
    MainOps -->|read/write contractual state| Artifacts
    MainOps -->|read/write contractual state| Claims
    MainOps -->|read/write contractual state| Decisions
    MainOps -->|read/write informational state| Summary

    Specs --- Similarity
    Artifacts --- Similarity
    Summary --- Similarity

    EvoRead -. read-only over live authority .-> Specs
    EvoRead -. read-only over live authority .-> Runs
    EvoRead -. read-only over live authority .-> Artifacts
    EvoRead -. read-only over live authority .-> Claims
    EvoRead -. read-only over live authority .-> Decisions
    EvoRead -. read-only over live authority .-> Summary

    EvoRead -->|append-only| EvoBatchStore
    EvoRead -->|proposal only| Handoff
    Handoff -->|if accepted| MainOps
```

## 3. Daily Main and Evolution Loop

This is the time-based relationship. Main runtime is real-time; evolution runs as a separate batch.

```mermaid
flowchart LR
    subgraph DayT["Day T"]
        Requests[User requests]
        AgentT[agent version T]
        MainT[main runtime]
        ArtifactsT[task records, docs, receipts, events]
    end

    subgraph NightT["Night T batch"]
        ReadDay[read today's runtime traces]
        EvalNight[evolution fitness and selection]
        CandidateState[candidate agent state update]
        ReviewGate[review-gated promotion]
    end

    subgraph DayT1["Day T+1"]
        AgentT1[agent version T+1]
        MainT1[next main runtime day]
    end

    Requests --> AgentT
    AgentT --> MainT
    MainT --> ArtifactsT

    ArtifactsT --> ReadDay
    ReadDay --> EvalNight
    EvalNight --> CandidateState
    CandidateState --> ReviewGate
    ReviewGate --> AgentT1

    AgentT1 --> MainT1
```

## 4. Turn-to-Arc Flow

This is the contract boundary inside a single turn. The agent may be stochastic internally, but the contract layer must become deterministic.

```mermaid
flowchart TD
    Input[User input and current repo state]
    Retrieval[retrieval and prior references]
    Internal[agent internal reasoning, memory, skills, prompts]
    Slots[structured slot output]
    Assemble[deterministic assembly and validation]
    Contract[contractual fields]
    Info[informational fields]
    Persist[task runtime persistence]
    Projection[derived artifact projection]

    Input --> Retrieval
    Retrieval --> Internal
    Input --> Internal
    Internal --> Slots
    Slots --> Assemble
    Assemble --> Contract
    Assemble --> Info
    Contract --> Persist
    Info --> Persist
    Persist --> Projection
```

Contractual fields are the governance boundary. Informational fields such as `summary` may help retrieval, but they must not weaken deterministic replay of the contract.

## 5. Artifact State Machine

This is the target artifact-state model. The current feature-task evaluator derives up to `promotable`; `promoted` remains reserved until it is backed by authoritative persisted state.

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> candidate: spec and implementation candidate exist
    candidate --> verified: required claims pass
    verified --> promotable: freshness, invariants, approvals
    promotable --> promoted: authoritative promotion receipt

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

## 6. Adapter Contract Map

External agents should connect through a narrow adapter contract rather than owning Sisyphus state directly.

```mermaid
flowchart LR
    subgraph External["External agent runtime"]
        Hermes[Hermes-like runtime]
        Claude[Claude Code]
        Other[other agent]
    end

    subgraph Adapter["Adapter layer"]
        Prompt[adapter prompt and schema]
        SlotWriter[slot writer]
        ReferenceWriter[reference capture]
    end

    subgraph Boundary["Deterministic contract boundary"]
        ContractFields[contractual fields]
        InfoFields[informational fields]
        Gate[main runtime validation and gates]
    end

    subgraph Runtime["Sisyphus main runtime"]
        TaskRuntime[task runtime]
        ArtifactView[derived artifact view]
    end

    Hermes --> Prompt
    Claude --> Prompt
    Other --> Prompt

    Prompt --> SlotWriter
    Prompt --> ReferenceWriter

    SlotWriter --> ContractFields
    ReferenceWriter --> InfoFields

    ContractFields --> Gate
    InfoFields --> Gate

    Gate --> TaskRuntime
    TaskRuntime --> ArtifactView
```

The adapter may vary by agent. The contract boundary may not.
