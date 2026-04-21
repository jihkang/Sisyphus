# Adaptive Planning Protocol

This document defines a draft planning protocol for Sisyphus.

The goal is not to force every task through the same design ceremony.
The goal is to let Sisyphus decide when extra design artifacts are worth creating, record that decision, and learn from whether that decision was correct.

## Why This Exists

Sisyphus should not require diagrams, extra specs, or design reviews for every task.

That would produce process noise on small work and would train the system to cargo-cult design artifacts instead of using judgment.

At the same time, Sisyphus should not leave design depth entirely implicit.

If a task needed structure work and the planner skipped it, that decision should be visible, reviewable, and correctable later.

The protocol is therefore:

- planning depth is adaptive
- the planner chooses the depth
- the choice must be justified
- later stages may judge that choice as correct or incorrect

## Core Rule

Sisyphus should treat planning depth as a first-class planning decision.

At planning time, the planner chooses a `design_mode`:

- `none`
- `light`
- `full`

That choice is part of the plan.

The choice should not be derived from a single hard-coded rule such as "always create diagrams when planning starts".
It should be made from the actual task shape.

## Design Modes

| Mode | Meaning | Typical Use |
| --- | --- | --- |
| `none` | No extra design artifacts are needed beyond the normal plan/spec text. | Local bug fixes, single-file edits, low-coupling changes, straightforward contract-preserving work. |
| `light` | A small amount of explicit design structure is useful, but full architectural treatment is unnecessary. | Changes that cross a few modules, adjust data flow, or introduce moderate workflow coupling. |
| `full` | The task changes system shape enough that explicit design artifacts are part of the work, not optional documentation. | New layers, new provider/runtime contracts, authority-boundary changes, workflow redesign, event-driven or multi-actor coordination changes. |

## Planner Responsibilities

When producing the plan, the planner should record:

- `design_mode`
- `design_decision_reason`
- `design_confidence`
- `required_design_artifacts`

The planner may also record:

- `design_risks`
- `design_unknowns`
- `operator_override_needed`

The point is not to produce a long essay.
The point is to make the planner's judgment legible.

## Layer-Related Planning

Some tasks do not just change behavior.
They change how responsibility is divided across the system.

For those tasks, the planner should explicitly judge whether the task is:

- layer-preserving
- layer-touching
- layer-reshaping
- layer-adding

This judgment matters because a task that changes layers usually needs more than an implementation checklist.

Typical signals include:

- a new boundary between orchestration and execution
- a new provider or runtime contract
- a new authority boundary
- a new adapter or routing layer
- movement of responsibilities from one module cluster to another
- a need to explain both static coupling and time-ordered behavior

When the task is `layer-reshaping` or `layer-adding`, the planner should usually avoid `design_mode = none`.

Useful recorded fields include:

- `layer_impact`
- `layer_decision_reason`
- `layer_artifacts_required`

Typical layer-oriented artifacts are:

- a connection or dependency mermaid
- a time-axis or sequence mermaid
- a boundary note describing authority, ownership, or promotion rules

The planner does not need to assume a single permanent layer model.
It only needs to record whether this task changes the effective system shape enough that later implementation and verification need a stable design anchor.

## Artifact Expectations By Mode

### `none`

Expected output:

- normal task plan
- normal verification strategy

Not expected by default:

- mermaid diagrams
- separate design memo
- architecture promotion candidate

### `light`

Expected output:

- normal task plan
- one compact design artifact when useful

Examples:

- one small mermaid connection graph
- one short interface sketch
- one short state or data-flow note

### `full`

Expected output:

- normal task plan
- explicit design artifacts that anchor later implementation and verification

Typical artifacts:

- structure or dependency mermaid
- time-axis, sequence, or lifecycle mermaid
- authority-boundary note
- interface or contract notes tied to the diagrams

These artifacts are task-local first.
They should not be promoted into shared architecture documents until implementation has actually landed and been verified.

## Diagram Rule

Diagrams are conditional artifacts, not mandatory rituals.

Sisyphus should not ask:

> did the planner create a diagram?

Sisyphus should ask:

> was the chosen design depth appropriate for the task?

That means a task may legitimately have:

- no diagram
- one lightweight diagram
- multiple diagrams

The quality of the decision matters more than the presence of a diagram.

## Planning Review Standard

Plan review should evaluate the planning-depth choice itself.

Reviewers should ask:

- Is `design_mode` too shallow for the actual risk?
- Is `design_mode` too heavy for the actual scope?
- Are the required artifacts enough for later verify and closeout?
- If no explicit design artifact was created, is that omission well justified?

This lets design depth become a reviewable part of planning rather than an unspoken assumption.

For layer-related work, reviewers should also ask:

- Did the planner identify that the task changes or adds a layer?
- If the task changes system boundaries, is there enough structure to verify the new boundary later?
- If a new adaptive layer is proposed, are both structural coupling and time-ordered behavior captured?

This is the main place where a missing layer model should be caught early rather than discovered only after code spreads across multiple modules.

## Spec Freeze Standard

If a task uses `light` or `full` mode and produces design artifacts that later implementation depends on, those artifacts should become part of the frozen task spec.

This does not mean every diagram becomes a permanent shared document.
It means the task's own frozen design anchor should be stable enough that verify can compare implementation against it.

Useful fields for a frozen anchor include:

- `design_mode`
- `frozen_design_artifacts`
- `design_anchor_summary`
- `layer_impact`
- `frozen_layer_model`

## Verify Standard

Verify should assess not only whether the implementation works, but whether the planning-depth decision was adequate.

Useful questions:

- Did the task need more explicit design structure than the planner provided?
- Did the created design artifacts actually help implementation and verification?
- Was the design burden excessive relative to the task?
- Did code and behavior drift from the frozen design anchor?
- Did the implementation reveal a layer change that the plan failed to model?
- If a new layer was introduced, was both its static placement and runtime role captured well enough?

This produces a post-hoc assessment of planning quality instead of treating the original planning decision as unquestionable.

## Post-Verify Design Assessment

Sisyphus should allow a short post-verify judgment such as:

- `design_assessment = appropriate`
- `design_assessment = underdesigned`
- `design_assessment = overdesigned`

With short supporting notes such as:

- implementation crossed more modules than expected
- hidden authority-boundary issues emerged during execution
- a lightweight plan would have been sufficient
- the task effectively introduced a new layer that the original plan did not model
- the layer model existed but did not capture the actual execution path

This is the main feedback loop that lets planning evolve naturally.

## Underdesign Recovery Loop

If a task is judged `underdesigned`, Sisyphus should not treat that only as a retrospective comment.
It should be able to trigger a bounded recovery loop.

The recovery loop is:

1. detect that the current plan is too shallow
2. record why it is too shallow
3. re-enter planning with a stricter design requirement
4. generate the missing artifacts or boundary notes
5. re-evaluate whether the plan is now adequate
6. continue implementation or verification from the revised anchor

This should be used especially when the missing structure is about layers, boundaries, or execution flow.

For example:

1. the original plan chose `design_mode = none`
2. review or execution reveals that the task actually introduces an adaptive layer
3. the task is marked `underdesigned`
4. planning is revised with `design_mode = full`
5. the revised plan adds a layer connection mermaid and a time-axis mermaid
6. plan review checks the revised design artifacts
7. implementation continues against the revised frozen anchor

The purpose of this loop is not to create endless replanning.
The purpose is to let Sisyphus recover when the original planning judgment was too weak.

Useful fields for this loop include:

- `design_escalation_required`
- `design_escalation_reason`
- `design_replan_round`
- `design_replan_artifacts`
- `design_replan_assessment`

This lets Sisyphus treat underdesign as an actionable planning problem, not just as a postmortem label.

## How Sisyphus Should Evolve

The long-term target is not:

- always generate diagrams

The long-term target is:

- improve the system's judgment about when structure is needed

That means Sisyphus should gradually learn from repeated outcomes such as:

- tasks with `none` mode that later proved underdesigned
- tasks with `full` mode that added little value
- task categories that consistently benefit from one specific artifact type
- tasks that repeatedly become `underdesigned` only when layer changes appear during execution
- tasks that need a second planning pass before adaptive or authority-boundary work becomes clear

The system should evolve its planning heuristics from audit feedback, not from rigid universal ceremony.

## Relationship To Shared Architecture Docs

Shared docs like `architecture.md` should describe implemented and verified system shape.

They should not become the first destination for speculative or task-local designs.

The promotion path should be:

1. task-local planning decision
2. task-local design artifacts when needed
3. frozen task-local spec anchor
4. implementation and verify
5. shared architecture sync if the design is now real

This keeps future design, active task design, and implemented architecture from collapsing into one document.

## Summary

Sisyphus should make design depth adaptive, explicit, and reviewable.

The planner should decide whether extra design artifacts are needed.
That decision should be recorded.
Later stages should assess whether the decision was good.

The system should improve by learning when design structure is actually useful, not by forcing the same ceremony on every task.
