# Brief

## Task

- Task ID: `TF-20260614-feature-add-eval-loop-runner`
- Type: `feature`
- Slug: `add-eval-loop-runner`
- Branch: `feat/add-eval-loop-runner`

## Problem

- Add explicit eval loop runner aligned with reward metrics
- Original request: Make the harness loop explicit without introducing online RL training yet.

Scope:
- Define an offline loop runner shape: observation_t -> action_t -> transition/result -> observation_t+1 -> reward/outcome.
- Align existing Sisyphus/evolution metrics with RewardBreakdown fields from reward.py.
- Add task outcome facts that can score closed, verified, failed, blocked, false-close, conformance-drift, missing-evidence, and excessive-action episodes.
- Add CLI/API surface for running a read-only or fixture-backed eval loop over recorded episodes/tasks.
- Represent the test-first loop as an explicit pending harness phase so future work can require test generation before implementation.
- Do not add PPO/GRPO or model training dependencies in this task.

Acceptance criteria:
- A closed verified task can be scored from task state plus episode/evidence artifacts.
- A failed or falsely closed task gets explicit penalty components.
- Metrics names are stable and documented in code tests.
- Tests show reward/eval consistency for at least passing, failed verification, conformance red/yellow, and missing evidence scenarios.
- The eval output exposes a test-first-loop TODO/phase without pretending that online test synthesis exists yet.

Dependency: episode trace and evidence graph improve this task, but a first version may run on task state plus existing reward.py.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] Offline eval loop result includes observation/action/reward/outcome structure.
- [ ] Reward metrics and eval metrics share stable names.
- [ ] Episode and evidence artifacts influence action count, missing evidence, and penalty facts.
- [ ] Test-first execution is visible as a future harness phase/TODO.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
