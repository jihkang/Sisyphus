# Migration And Runtime Sequence

## Target Runtime Sequence

```mermaid
sequenceDiagram
    actor Operator
    participant Interface as CLI/MCP/API adapter
    participant Bootstrap as Composition root
    participant UseCase as Application use case
    participant Policy as Domain policy
    participant Repo as TaskRepository port
    participant Effect as Provider/Verifier/Git/Event port
    participant Infra as Concrete infrastructure adapter

    Operator->>Interface: transport request
    Interface->>Bootstrap: resolve repository application
    Bootstrap-->>Interface: configured use case
    Interface->>UseCase: typed command
    UseCase->>Repo: load aggregate/snapshot
    Repo->>Infra: concrete file operation
    Infra-->>Repo: persisted record
    Repo-->>UseCase: domain model
    UseCase->>Policy: evaluate transition
    Policy-->>UseCase: typed decision and gates
    alt decision permits side effect
        UseCase->>Effect: execute bounded effect
        Effect->>Infra: provider/verifier/Git/event implementation
        Infra-->>Effect: typed receipt
        Effect-->>UseCase: typed receipt
        UseCase->>Repo: compare-and-update state
    end
    UseCase-->>Interface: typed result
    Interface-->>Operator: stable CLI/MCP/API projection
```

## Per-Use-Case Cutover

```mermaid
stateDiagram-v2
    [*] --> Characterized
    Characterized --> PortDefined: baseline output and failure tests exist
    PortDefined --> LegacyAdapter: current function implements inward port
    LegacyAdapter --> ParityProven: old and application paths agree
    ParityProven --> ConcreteAdapter: implementation moves outward
    ConcreteAdapter --> InterfaceWired: composition root selects adapter
    InterfaceWired --> ShimOnly: public facade delegates
    ShimOnly --> LegacyRemoved: import search and wheel tests prove no owner remains
    LegacyRemoved --> [*]
```

No use case skips the characterization, parity, or shim stages. Persisted schema changes are outside this sequence and require a separate approved task.

## Failure Ordering

Application use cases must make effect order explicit. A state update that records an external effect occurs only after a typed receipt is returned. Retry paths inspect existing state/receipts before repeating commit, push, PR, verification, or event operations. Failure-injection tests stop after each boundary and compare the resulting task record and artifacts to the baseline contract.
