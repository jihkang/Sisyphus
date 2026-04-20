# Brief

## Task

- Task ID: `TF-20260420-feature-unify-evolution-events-under-envelope-bus`
- Type: `feature`
- Slug: `unify-evolution-events-under-envelope-bus`
- Branch: `feat/unify-evolution-events-under-envelope-bus`

## Problem

- The evolution stack now persists read-only runs, follow-up bridge artifacts, receipt projections, verification projections, and promotion/invalidation envelopes, but those slices do not emit a consistent evolution-scoped event stream.
- Without explicit envelope-bus events, downstream automation has to infer evolution state by polling files instead of consuming a stable domain event trail.
- This slice should add evolution-scoped event envelopes only. It must not add new CLI/MCP commands, orchestration loops, or policy decisions.

## Desired Outcome

- Existing evolution slices publish a stable event vocabulary under the repository envelope bus.
- The event stream preserves run, candidate, and follow-up task lineage so later automation can correlate the hard-state artifacts without re-parsing the entire filesystem.
- The change remains narrow: publish events from existing slices and add focused tests only.

## Acceptance Criteria

- [ ] `execute_evolution_run` emits evolution run events for both recorded and failed runs with run ID, final stage, artifact directory, and persisted artifact context.
- [ ] `bridge_evolution_followup_request`, `project_followup_execution`, and `project_followup_verification` emit evolution lineage events with run ID, candidate ID, and follow-up task linkage.
- [ ] `record_evolution_decision_envelope` emits a decision event that distinguishes promotion vs invalidation outcomes without adding new runtime surfaces.
- [ ] Focused unit tests cover the new evolution event envelopes and keep the scope out of CLI/MCP surface additions or orchestration loops.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add new CLI/MCP commands, orchestration loops, or policy derivation in this slice.
- Use the existing repository envelope bus (`.planning/events.jsonl` via configured event bus publisher) instead of introducing a second event sink.
