# LinkedIn Weekly Main Summary

This document summarizes the state of Sisyphus from one week ago to the current `origin/main` branch, in a format that can be adapted for LinkedIn.

## Scope

- Summary window: `2026-04-10` to `2026-04-17`
- Baseline mainline snapshot before the window: `327e31f` on `2026-04-06`
  - `Merge pull request #4 from jihkang/feat/sisyphus-worker-discipline`
- Current `origin/main` head inspected for this summary: `48d9ee4` on `2026-04-17`

This summary is based on `origin/main`, not on local feature branches or unmerged work.

## One-Week-Ago Snapshot

As of `2026-04-10`, `main` was still effectively at the `2026-04-06` mainline state.

At that point, Sisyphus already had:

- repository-local task orchestration
- plan and follow-up gates
- worker discipline and execution control
- task/worktree-based workflow management

At that point, `main` did not yet include the newer foundations that now define the project:

- event bus and conformance tracking
- official SDK-based MCP gateway/core split
- evolution control-plane foundation
- canonical `sisyphus.*` public naming surface
- task-record locking improvements

## What Landed On Main Since Then

Between `2026-04-10` and `2026-04-17`, `origin/main` absorbed:

- `12` commits total
- `8` non-merge commits
- `4` merge commits on the first-parent mainline
- `104` changed files
- `9,228` insertions and `370` deletions

## Mainline Milestones

### 1. Direct-change adoption for task requests

Mainline landing:

- `2026-04-13`
- `eeb81ff`
- `Merge pull request #5 from jihkang/feat/direct-change-adoption`

What changed:

- task requests gained a direct-change adoption path
- daemon and gitops logic were extended so current branch changes can be pulled into task execution flow
- taskflow API and CLI behavior became more practical for ongoing in-repo work

Why it matters:

- operators no longer have to treat every request as a clean-room start
- Sisyphus became better aligned with real feature branches and active working trees

### 2. Event bus, conformance model, and SDK-based MCP support

Mainline landing:

- `2026-04-13`
- `952fae4`
- `Merge pull request #6 from jihkang/feat/event-bus-mcp-sdk`

What changed:

- added event bus abstraction and JSONL-backed event publishing
- added a `green / yellow / red` conformance model and persistence
- introduced an MCP core service plus official SDK-based stdio MCP gateway
- added operator-facing architecture and MCP client setup docs
- added setup flows and wrappers for Codex and Claude

Why it matters:

- Sisyphus moved from a local task runner toward an inspectable control plane
- Codex, Claude, and future clients now have a stable interface into repo-local state
- task progress became easier to observe, audit, and integrate with other tools

### 3. Evolution foundation and evaluation-loop architecture

Mainline landing:

- `2026-04-14`
- `a06d90a`
- `Merge pull request #8 from jihkang/feat/evolution-foundation`

What changed:

- added `src/taskflow/evolution/` with targets, dataset extraction, harness planning, constraints, fitness scoring, reporting, and run planning
- documented the architecture and self-evolution direction in repo docs
- added dedicated tests for the evolution surface

Why it matters:

- Sisyphus gained the foundation for a separate evolution control plane
- the project is no longer only about task execution; it now has a measurable path toward evaluating and improving its own policies and workflows

### 4. Reliability improvements for task state

Mainline landing:

- `2026-04-15`
- `dda2fb5`
- `lock task records and share utc helper`

What changed:

- task record writes were hardened with locking-oriented changes
- shared UTC timestamp handling was introduced across task-state paths
- audit, closeout, planning, daemon, state, and workflow flows were tightened

Why it matters:

- repository-local state became safer under repeated updates
- task lifecycle transitions became more consistent and less timing-sensitive

### 5. Public naming cleanup from `taskflow` to `sisyphus`

Mainline landing:

- current `origin/main` includes `33220cf`
- surfaced on mainline by `2026-04-17` head `48d9ee4`

What changed:

- canonical public entrypoints moved toward `sisyphus.*`
- added `sisyphus.cli`, `sisyphus.mcp_server`, and `sisyphus.evolution`
- kept `taskflow` compatibility in place while shifting docs, wrappers, and tests toward the preferred name

Why it matters:

- the product surface is now easier to explain publicly
- the repository now presents a clearer identity without forcing a breaking rename

## Condensed Before/After

### Before (`2026-04-10`)

- Sisyphus was already a repository-local orchestration system with gated workflow control.
- The public/runtime story was still mostly task-centric and `taskflow`-named.
- There was no event-driven observability layer, no MCP-first integration surface, and no evolution foundation on `main`.

### After (`2026-04-17`)

Sisyphus is now a repository-local orchestration system with:

- event publishing and conformance tracking
- an official MCP gateway/core split for agent clients
- architecture documentation and client setup docs
- an evolution control-plane foundation
- safer task record persistence
- a clearer `sisyphus` public naming surface

## Suggested LinkedIn Angle

The strongest public framing is:

- this was not a cosmetic week
- the work moved Sisyphus from "task runner" toward "observable, MCP-addressable orchestration system"
- the evolution foundation shows a credible path toward self-improving workflows

## LinkedIn Draft: English

Over the last week, I pushed Sisyphus from a repository-local task runner into a more complete orchestration platform.

On `main`, the system gained event-bus and conformance foundations, an official SDK-based MCP gateway/core split for agent clients, a read-only evolution control plane for evaluating workflow improvements, task-record locking for more reliable repo-local state, and a clearer public `sisyphus` naming surface while preserving backward compatibility.

The practical result is a system that is easier to operate, easier to integrate with tools like Codex and Claude, and better positioned for measured self-improvement instead of ad hoc agent behavior.

This was a meaningful step from “automating tasks” toward “building a controllable work system.”

## LinkedIn Draft: Korean

지난 1주일 동안 Sisyphus를 단순한 repository-local task runner에서, 좀 더 명확한 orchestration platform으로 밀어올리는 작업을 진행했습니다.

`main` 기준으로 보면 event bus와 conformance 추적, 공식 SDK 기반 MCP gateway/core 분리, workflow 개선을 평가하기 위한 evolution control plane 기초, task record locking을 통한 상태 안정화, 그리고 `taskflow`에서 `sisyphus`로 이어지는 공개 naming surface 정리가 들어갔습니다.

결과적으로 Sisyphus는 이제 더 잘 관측되고, Codex/Claude 같은 에이전트 클라이언트와 연결하기 쉬워졌으며, 즉흥적인 agent loop가 아니라 측정 가능한 작업 시스템으로 발전할 기반을 갖추게 됐습니다.

## Short Version

In one week, `main` moved from a gated repo-local workflow runner to a more observable and extensible orchestration system:

- direct-change adoption for task requests
- event bus + conformance tracking
- MCP gateway/core and client setup
- evolution evaluation foundation
- task-state reliability improvements
- canonical `sisyphus` public surface

## Source Commits

Mainline commits used as the narrative anchors:

- `eeb81ff` on `2026-04-13` — merge of direct-change adoption
- `952fae4` on `2026-04-13` — merge of event bus, conformance, and SDK MCP work
- `a06d90a` on `2026-04-14` — merge of evolution foundation
- `dda2fb5` on `2026-04-15` — task record locking and UTC utility cleanup
- `48d9ee4` on `2026-04-17` — mainline head including naming unification work

## Notes

- The wording above is intentionally LinkedIn-friendly, not release-note-complete.
- It is safe to trim the draft further if a shorter post is preferred.
