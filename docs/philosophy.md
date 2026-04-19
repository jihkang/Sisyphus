# Sisyphus Philosophy

Sisyphus exists to turn AI-assisted work into a system that can be repeated, reproduced, confirmed, and inspected.

The goal is not only to make the model think better.
The goal is to make better thinking produce real system changes, with evidence that another operator can review and trust.

## Core Principles

### 1. Repeatable

Work should be runnable again without relying on hidden context in the operator's head.

- Task state must be explicit.
- Execution steps must be recoverable.
- The next action should be derivable from recorded state.

### 2. Reproducible

Results should be reproducible by another operator, in another session, from the task record and repository state.

- Important decisions must leave traceable artifacts.
- Verification must point to concrete steps, commands, or observations.
- Success must not depend on the presence of the original agent.

### 3. Confirmable

Claims are not enough. The system should prefer evidence over confidence.

- Do not treat explanation as proof.
- Prefer executed checks to inferred correctness.
- Record what was actually observed, not only what was intended.

### 4. Inspectable

A task should remain understandable to a third party who did not participate in the original work.

- State transitions must be visible.
- Gates and blockers must be explicit.
- The reasoning behind approval, verification, and closeout should be reviewable.

## Thinking Discipline

Sisyphus should adopt a strict execution discipline for every worker and subtask.

### Break It

Before accepting a conclusion, look for the condition under which it fails.

- Identify assumptions before acting.
- Seek counterexamples early.
- Treat confidence as a trigger for verification, not a substitute for it.

### Cross It

Reach the same conclusion through an independent path when the cost is reasonable.

- Use a second tool, second method, or second perspective.
- Compare prediction against observation.
- Call out divergence explicitly.

### Ground It

Anchor conclusions in reality.

- Run the code.
- Read the files.
- Inspect the logs.
- Observe the system state.

The model's internal picture is never enough on its own.

## Worker Prompt Principles

Every worker prompt should reinforce the following behavior.

### 1. Change the system, not only the explanation

The objective is not a plausible story. The objective is a concrete, reviewable change to the repository or task state.

### 2. State assumptions and uncertainty

Workers should identify:

- what they know
- what they infer
- what they still need to verify

### 3. Verify at the point of action

Do not postpone verification until the very end if a small check can reduce downstream risk.

### 4. Preserve evidence

Workers should leave enough evidence for another operator to:

- understand what changed
- reproduce the result
- inspect whether the conclusion is justified

### 5. Escalate at judgment boundaries

Automation should stop when human judgment is the real blocker.

- plan approval
- ambiguous tradeoffs
- unclear requirements
- unverified high-risk changes

## Plan Standard

A task plan should do more than list implementation steps.

Each plan should answer:

- What will change?
- Why is this the right change?
- What can fail?
- How will the result be reproduced?
- How will the result be verified independently?
- What evidence will justify closing the task?

In practice, a plan should cover:

- implementation plan
- reproduction plan
- verification plan
- inspection plan

## Verify Standard

Verification is the stage where confidence must be converted into evidence.

Sisyphus verify should answer:

### 1. Was the task implemented as claimed?

- The claimed behavior exists in code or configuration.
- The task docs match the actual implementation scope.

### 2. Can the result be reproduced?

- There is a clear path to reproduce the behavior.
- Relevant commands, inputs, or conditions are recorded.

### 3. Was the result confirmed, not assumed?

- Commands were executed when feasible.
- Logs, outputs, diffs, or observable state support the claim.
- Unsupported claims are treated as unresolved.

### 4. Were failure paths checked?

- At least one counterexample, edge case, or exception path was considered.
- Verification does not only cover the happy path.

### 5. Is the result inspectable by another operator?

- A reviewer can tell what was changed.
- A reviewer can see what evidence supports the conclusion.

## Close Standard

Close does not mean "the agent is finished talking."
Close means "the work is complete enough that another operator can trust the result."

A task should be closable only when:

### 1. The result is verified

- Verification passed with no blocking gates.

### 2. The task can be revisited and understood

- The task record is coherent.
- The implementation scope matches the docs.
- The outcome is not dependent on hidden operator memory.

### 3. The result can be inspected later

- A future reviewer can trace why the task was considered complete.
- Important evidence is still available through task files, code, or repository history.

### 4. Remaining risk is explicit

- If something was intentionally deferred, that fact should be visible.
- If a follow-up task is needed, the relationship should be recorded.

## Operational Rule

Sisyphus should automate execution aggressively, but automate judgment conservatively.

That means:

- automate setup
- automate state transitions
- automate worker execution
- automate routine checks
- stop before human approval boundaries
- stop when evidence is insufficient

For the evolution subsystem, this rule is stricter:

- automate candidate planning and read-only evaluation
- allow isolated evidence gathering
- do not let evolution approve its own work
- do not let evolution freeze specs or promote results
- require the normal Sisyphus lifecycle for any live repository change

## Summary

Sisyphus is not only a task runner and not only a thinking aid.

It is a system for making AI work:

- think critically
- change real systems
- leave reproducible evidence
- remain inspectable after the original session ends
