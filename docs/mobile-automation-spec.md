# Phone-First Automation Spec

This document defines an OpenClaw-style automation model for Sisyphus with a phone-first operator loop.

The goal is not to build a separate mobile app first. The goal is to let an operator trigger, observe, and approve automation from a phone with minimal latency, using surfaces that already exist in the repository.

## Problem

Sisyphus already has:

- repository-local task orchestration
- a daemon and service loop
- Discord intake and outbound notifications
- remote/mobile bridge concepts in the bundled `cc` code

What it does not yet have is a single automation spec that ties those parts together into an operator experience:

- automation should keep moving without sitting in a terminal
- state changes should become mobile-friendly notifications
- an operator should be able to review and respond from a phone
- deeper inspection should be one tap away instead of requiring local shell access

## Product Goal

Sisyphus should support a persistent automation runner that:

1. watches task and event state continuously
2. triggers predefined automation rules
3. emits structured notifications to a phone-friendly surface
4. supports lightweight operator actions from chat/mobile
5. escalates into a richer remote session only when needed

The intended behavior is "automation by default, human intervention by exception".

## Design Principles

- Reuse the current file-first task model. Do not introduce a database for MVP.
- Make Discord the first mobile surface because the repository already has end-to-end intake and notification plumbing there.
- Treat remote/mobile session URLs as a drill-down path, not as the primary status surface.
- Keep automation rules explicit and reviewable in repository config.
- Separate read-only notifications from write-capable automation actions.
- Make approval boundaries obvious. Phone interaction must be safe even when terse.

## Existing Building Blocks

The current repository already contains the minimum substrate for this feature:

- `src/sisyphus/discord_bot.py`
  inbound message intake and outbound task notifications
- `src/sisyphus/service.py`
  state-diff tracking and notification summaries
- `src/sisyphus/workflow.py`
  deterministic task/subtask progression and event emission
- `src/sisyphus/api.py`
  request and queue entrypoints that can be reused by automation rules
- `cc/commands/session/session.tsx`
  QR-code and remote session URL presentation
- `cc/hooks/useRemoteSession.ts`
  remote/mobile session state and background task counters

This means the MVP does not need a new transport. It needs an automation layer and a better operator contract.

## User Stories

### 1. Mobile monitoring

An operator is away from the laptop and wants to know whether a task is blocked, waiting on approval, or failed verify.

Success criteria:

- a notification arrives within seconds of the transition
- the message contains task id, phase, conformance summary, and next action
- the operator does not need to SSH or open a terminal to understand the state

### 2. Mobile approval

An operator receives a "plan in review" or "needs user input" notification and wants to approve, request changes, or retry from a phone.

Success criteria:

- the action can be issued from the primary phone surface
- the action is authenticated to an allowed operator identity
- the action is written back into normal Sisyphus task state, not a side channel

### 3. Drill-down inspection

An operator wants more than a short summary and needs a richer live session view.

Success criteria:

- the notification contains a deep link or session reference
- the richer session can be opened from a mobile browser without losing task context
- this path is optional, not required for routine monitoring

## Proposed Product Surface

The system should be exposed as three layers.

### Layer 1. Automation runner

A long-lived runner evaluates rules and performs safe actions against the repo-local Sisyphus state.

Responsibilities:

- watch task JSON, inbox events, and emitted workflow events
- evaluate rule triggers
- invoke actions such as notify, queue task, request task, rerun verify, or mark review transitions
- enforce safety policy before any write-capable action

### Layer 2. Mobile notification surface

Discord is the first-class notification and response surface for MVP.

Responsibilities:

- receive concise state-change notifications
- show task id, phase, plan/spec state, gates, and conformance summary
- expose simple operator actions through reply commands or structured bot commands

### Layer 3. Deep drill-down surface

The bundled `cc` remote/mobile bridge becomes the optional "open full session" path.

Responsibilities:

- provide a live URL or session handle when a task requires more context
- show remote background task counts and streaming updates
- remain secondary to the notification flow

## Proposed Automation Configuration

Automation should live in repo config, next to other Sisyphus behavior.

Suggested shape:

```toml
[automation]
enabled = true
poll_interval_seconds = 10
max_actions_per_cycle = 5

[automation.mobile]
primary_surface = "discord"
deep_link_surface = "remote_session"
notification_verbosity = "compact"

[automation.discord]
channel_ids = ["12345"]
allowed_operator_ids = ["u_1", "u_2"]
send_thread_replies = true

[[automation.rules]]
id = "notify-plan-review"
trigger.kind = "task_transition"
trigger.workflow_phase = "plan_in_review"
action.kind = "notify"
action.template = "approval_needed"

[[automation.rules]]
id = "notify-verify-failure"
trigger.kind = "event"
trigger.event_type = "verify.completed"
trigger.status = "failed"
action.kind = "notify"
action.template = "verify_failed"

[[automation.rules]]
id = "nightly-triage"
trigger.kind = "cron"
trigger.cron = "0 */2 * * *"
action.kind = "request_task"
action.title = "Nightly blocked-task triage"
action.message = "Summarize blocked tasks and propose next actions."
action.auto_run = false
```

## Trigger Model

The MVP trigger model should stay narrow.

Supported trigger families:

- `task_transition`
  task status, phase, plan/spec state, or gate changes
- `event`
  emitted workflow events such as `subtask.failed` or `verify.completed`
- `cron`
  periodic summary or maintenance jobs
- `operator_command`
  inbound command from Discord or another mobile surface

Non-goal for MVP:

- arbitrary free-form policy code execution

## Action Model

Actions should be typed and safety-checked.

Suggested action kinds:

- `notify`
  send a structured notification only
- `queue_conversation`
  enqueue a human-authored follow-up request
- `request_task`
  create a new task from a rule
- `plan_approve`
- `plan_request_changes`
- `spec_freeze`
- `run_verify`
- `close_task`
- `open_remote_session_link`
  generate or attach the drill-down URL only

Write-capable actions must declare intent up front and be deny-by-default unless explicitly enabled.

## Notification Contract

The phone surface should receive structured notifications, not a single opaque summary string.

Suggested payload model:

```json
{
  "task_id": "TF-20260416-feature-example",
  "title": "Example task",
  "status": "blocked",
  "workflow_phase": "needs_user_input",
  "plan_status": "approved",
  "spec_status": "frozen",
  "conformance": "yellow checkpoint=post_exec drift=1",
  "gates": ["VERIFY_FAILED"],
  "summary": "verify failed after all subtasks completed",
  "next_actions": ["retry_verify", "request_changes", "open_session"],
  "deep_link": "https://...",
  "source_context": {
    "kind": "discord",
    "channel_id": "12345",
    "thread_id": "67890"
  }
}
```

The current `TaskNotification.summary` string can remain as a rendering fallback, but the automation layer should work from structured data.

## Mobile Operator Commands

For MVP, operator commands should be plain, explicit, and parseable from chat.

Examples:

- `status TF-20260416-feature-example`
- `approve TF-20260416-feature-example`
- `request-changes TF-20260416-feature-example reason...`
- `freeze-spec TF-20260416-feature-example`
- `retry-verify TF-20260416-feature-example`
- `open-session TF-20260416-feature-example`

Rules:

- commands must map to existing Sisyphus transitions or APIs
- commands must reject unknown task ids and disallowed users
- commands must emit a confirmation message back to the same mobile surface

## Safety Model

Phone-first automation is only useful if it is hard to misuse.

MVP safety requirements:

- per-surface allowlist of operator identities
- no destructive git actions from mobile commands
- no auto-merge, force-push, or branch deletion
- no write-capable automation rule without explicit config
- every rule action produces an audit event
- every operator command produces a task or event log trail

Recommended policy split:

- read-only rules enabled broadly
- write-capable rules enabled narrowly
- approval-style actions require explicit operator identity

## Architecture Changes

### New module: automation runner

Introduce a module shaped like:

- `src/sisyphus/automation.py`
  config parsing, rule evaluation, action dispatch

Possible supporting modules:

- `src/sisyphus/automation_rules.py`
- `src/sisyphus/automation_notifications.py`

### Service integration

`service.py` should expose structured state-change data, not only summary strings.

Needed evolution:

- preserve current summary text
- add machine-readable notification payloads
- let sinks render payloads differently for Discord vs remote session vs future web surface

### Discord integration

`discord_bot.py` should grow from simple intake + summary posting into a mobile operator interface.

MVP additions:

- parse operator commands
- authorize commands against config
- reply with task summaries or action results
- attach compact status blocks to notifications

### Deep-link integration

The `cc` remote session layer should not be required for routine monitoring.

It should be used when:

- a task enters repeated failure or unresolved review loops
- an operator explicitly requests a deeper view
- the system wants to hand off from notification to live interactive inspection

## MVP Slices

Implement this in four slices.

### Slice 1. Structured notifications

Deliverables:

- typed notification payload model
- service-level diffing that includes gates and conformance
- Discord rendering for compact mobile updates

Outcome:

- phone users can understand task state from notifications alone

### Slice 2. Mobile operator commands

Deliverables:

- Discord command parser
- allowlisted operator identities
- bindings for status, plan approve, request changes, spec freeze, verify retry

Outcome:

- basic review and retry flows work entirely from phone chat

### Slice 3. Automation rules engine

Deliverables:

- automation config schema
- event/task/cron triggers
- safe action dispatcher

Outcome:

- Sisyphus can run OpenClaw-style recurring automation without manual terminal babysitting

### Slice 4. Deep drill-down links

Deliverables:

- remote session link generation contract
- mobile-friendly attachment of session URLs to selected notifications
- escalation rules for when a live session link should be offered

Outcome:

- complicated failures can be inspected from a phone without re-deriving context

## Out of Scope

These should stay out of the MVP:

- a brand-new native mobile app
- push notification infrastructure outside existing chat/remote surfaces
- autonomous git merge/release flows
- general-purpose arbitrary automation scripting
- replacing repository-local task state with a hosted backend

## Verification Plan

The spec is correct when the following are true:

- every required capability maps onto an existing repository seam or a clearly named new module
- Discord is sufficient for the first operator loop
- the remote session bridge is treated as drill-down, not the primary monitoring path
- automation actions are typed and safety-scoped
- the MVP slices can be implemented independently

## Recommended Next Task Order

1. implement structured mobile notification payloads and Discord rendering
2. implement Discord operator commands for status and approval actions
3. add automation config parsing and a rule evaluator
4. connect selected notifications to remote session drill-down links

## Summary

The correct first version of "OpenClaw-like automation for Sisyphus" is:

- Discord for immediate phone-native status and approvals
- service/workflow events as the source of automation triggers
- repository config as the source of automation rules
- remote/mobile session links as an escalation path

That is the shortest path to useful phone-first automation without introducing a second orchestration system.
