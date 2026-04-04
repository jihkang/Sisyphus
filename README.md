# Sisyphus

Sisyphus는 `git worktree` 기반 task lifecycle과 Codex worker 실행 추적을 제공하는 Python CLI입니다.

현재 코드베이스의 핵심 목표는 다음입니다.

- task 생성부터 spec 작성, verify, close까지 공용 흐름으로 맞춘다.
- 서브 에이전트가 무엇을 실행 중인지 task 단위로 기록하고 조회한다.
- 대화 입력을 inbox 이벤트로 받아 task를 자동 생성하고 Codex worker를 실행한다.

## 핵심 워크플로

### 1. 수동 task 생성

`taskflow new feature <slug>` 또는 `taskflow new issue <slug>`를 실행하면 다음 순서로 처리됩니다.

1. repo root를 찾는다.
2. `.taskflow.toml`을 읽어 base branch, worktree root, branch prefix를 결정한다.
3. task id와 branch/worktree 경로를 계산한다.
4. 실제 `git worktree add -b <branch> <path> <base-ref>`를 실행한다.
5. `.planning/tasks/<task-id>/task.json`과 문서 템플릿을 생성한다.
6. 실패 시 branch, worktree, task directory를 rollback한다.

즉 metadata만 만드는 것이 아니라 실제 Git branch와 worktree까지 생성한다.

### 2. 대화 기반 task 생성

대화 입력을 직접 task로 승격하려면 inbox 이벤트를 만든 뒤 daemon이 처리하게 하면 됩니다.

```bash
uv run python -m taskflow.cli ingest conversation "에이전트 상태 대시보드를 추가해줘"
uv run python -m taskflow.cli daemon --once
```

`conversation` 이벤트는 다음 순서로 처리됩니다.

1. `.planning/inbox/pending/*.json`에 이벤트를 기록한다.
2. `taskflow daemon`이 pending 이벤트를 읽는다.
3. `taskflow new`와 같은 방식으로 task, branch, worktree를 만든다.
4. 대화 내용을 기반으로 `BRIEF.md`, `PLAN.md` 또는 `REPRO.md`, `FIX_PLAN.md` 초안을 자동으로 채운다.
5. 기본 설정이면 로컬 `codex exec`를 worker로 실행한다.
6. 결과를 `.planning/inbox/processed` 또는 `.planning/inbox/failed`로 이동하고 `.planning/events.jsonl`에 append-only 로그를 남긴다.

### 3. Spec 작성과 verify

`taskflow verify <task-id>`는 spec-first 방식으로 동작한다.

처리 순서:

1. 문서가 템플릿 상태인지 검사한다.
2. feature면 acceptance criteria, issue면 repro/regression target이 채워졌는지 검사한다.
3. `PLAN.md` 또는 `FIX_PLAN.md`에서 normal / edge / exception case와 verification mapping을 파싱해 `task.json`에 반영한다.
4. spec gate가 모두 해소된 경우에만 verify command를 실행한다.
5. 결과를 `VERIFY.md`와 `task.json`에 기록한다.

### 4. Close

`taskflow close <task-id>`는 아래 조건을 만족해야 성공한다.

- `verify_status == passed`
- unresolved gate 없음
- worktree 또는 repo가 dirty 하지 않음

dirty 상태인데도 닫아야 하면 `--allow-dirty`를 사용할 수 있다.

### 5. Agent 추적

각 task 아래 `agents/*.json`을 두고 agent 상태를 기록한다.

직접 기록하는 raw status:

- `queued`
- `running`
- `waiting`
- `completed`
- `failed`
- `cancelled`

파생 status:

- `stale`

`stale`은 raw status가 아니라 heartbeat 시간으로 계산되는 상태다. 기본 stale 기준은 900초다.

## CLI 사용법

설치 없이 바로 실행:

```bash
uv run python -m taskflow.cli <command>
```

설치 후 실행:

```bash
taskflow <command>
```

### Task 관련

```bash
uv run python -m taskflow.cli new feature sample-task
uv run python -m taskflow.cli new issue broken-login

uv run python -m taskflow.cli verify TF-20260405-feature-sample-task
uv run python -m taskflow.cli close TF-20260405-feature-sample-task
uv run python -m taskflow.cli close TF-20260405-feature-sample-task --allow-dirty

uv run python -m taskflow.cli status
uv run python -m taskflow.cli status --blocked
uv run python -m taskflow.cli status --open
uv run python -m taskflow.cli status --json
uv run python -m taskflow.cli status --agents
```

### Conversation intake / daemon

대화 입력을 inbox에 넣는다:

```bash
uv run python -m taskflow.cli ingest conversation "에이전트 상태 대시보드를 추가해줘"
```

옵션을 더 주면 task type, slug, instruction, provider를 같이 넣을 수 있다.

```bash
uv run python -m taskflow.cli ingest conversation \
  "verify 실패 원인을 먼저 분석한 뒤 수정해줘" \
  --title "Fix verify regression" \
  --task-type issue \
  --slug fix-verify-regression \
  --instruction "focus on the failing regression path first" \
  --agent-id worker-main \
  --provider codex
```

Codex 실행 없이 task만 만들고 싶으면:

```bash
uv run python -m taskflow.cli ingest conversation "초안만 만들고 아직 실행하지 마" --no-run
```

daemon을 한 번만 돌려 pending 이벤트를 처리:

```bash
uv run python -m taskflow.cli daemon --once
```

백그라운드 poller처럼 계속 돌리려면:

```bash
uv run python -m taskflow.cli daemon --poll-interval-seconds 5
```

테스트나 점진 배포용으로 처리 개수를 제한하려면:

```bash
uv run python -m taskflow.cli daemon --once --max-events 1
```

### Agent 관련

수동 lifecycle 기록:

```bash
uv run python -m taskflow.cli agent start <task-id> worker-1 --role worker --step "editing tests"
uv run python -m taskflow.cli agent update <task-id> worker-1 --status waiting --step "waiting for review"
uv run python -m taskflow.cli agent finish <task-id> worker-1 --status completed --summary "done"

uv run python -m taskflow.cli agents
uv run python -m taskflow.cli agents --task-id <task-id>
uv run python -m taskflow.cli agents --task-id <task-id> --json
```

명령 실행과 추적을 같이 묶고 싶을 때:

```bash
uv run python -m taskflow.cli agent run <task-id> worker-1 \
  --role worker \
  --provider codex \
  --step "editing tests" \
  -- python -c "print('ok')"
```

이 명령은 다음을 자동으로 처리한다.

- 시작 시 `running` 등록
- subprocess pid, command, summary 기록
- heartbeat 갱신
- 종료 코드에 따라 `completed` 또는 `failed` 처리
- stdout 일부를 `last_message_summary`로 반영

## Provider wrapper

`wrappers/codex`와 `wrappers/claude`는 `agent run`을 감싼 thin wrapper다.

### Codex wrapper

`wrappers/codex/run.py`는 기본적으로 로컬 `codex exec`를 호출한다.

동작:

1. `<task-id>`의 `task.json`과 task 문서를 읽는다.
2. Codex용 프롬프트를 자동 구성한다.
3. 로컬 `codex exec -C <worktree> -`를 실행하고 prompt를 stdin으로 넘긴다.
4. stdout은 터미널에 그대로 출력한다.
5. 출력 일부를 `last_message_summary`로 자동 반영한다.

이미 있는 task를 바로 실행:

```bash
python wrappers/codex/run.py <task-id> worker-1 --role worker
```

대화 한 줄로 task 생성까지 같이 처리:

```bash
python wrappers/codex/run.py conversation "에이전트 상태 대시보드를 추가해줘" --agent-id worker-1
```

이 모드는 내부적으로 다음을 자동으로 처리한다.

1. conversation event를 만든다.
2. task, branch, worktree, 문서 초안을 생성한다.
3. 생성된 task를 기준으로 `codex exec`를 바로 실행한다.
4. 결과는 inbox/event log에도 그대로 남긴다.

기존 task 기준 기본 실행:

```bash
python wrappers/codex/run.py <task-id> worker-1 --role worker
```

추가 지시 포함:

```bash
python wrappers/codex/run.py <task-id> worker-1 \
  --role worker \
  --instruction "focus on failing tests first"
```

Codex 인자 추가:

```bash
python wrappers/codex/run.py <task-id> worker-1 \
  --provider-arg=--full-auto \
  --provider-arg=--json
```

daemon도 내부적으로 같은 wrapper 경로를 사용한다.

### Claude wrapper

`wrappers/claude/run.py`는 아직 기본 Claude 실행 로직은 없다.

현재는 수동 명령을 tracked wrapper로 실행하는 용도다.

```bash
python wrappers/claude/run.py <task-id> worker-2 --role explorer -- python -c "print('ok')"
```

## 상태 파일 구조

```text
.planning/
  events.jsonl
  inbox/
    pending/
    processed/
    failed/
  tasks/
    <task-id>/
      task.json
      BRIEF.md
      PLAN.md / FIX_PLAN.md
      REPRO.md
      VERIFY.md
      LOG.md
      agents/
        <agent-id>.json
```

- `events.jsonl`: inbox 처리 이력
- `inbox/pending`: 아직 처리하지 않은 이벤트
- `inbox/processed`: 성공적으로 task 생성 및 dispatch가 끝난 이벤트
- `inbox/failed`: 처리 중 오류가 난 이벤트
- `task.json`: task lifecycle 상태
- `agents/*.json`: agent 상태

## `.taskflow.toml`

설정 파일이 없으면 아래 기본값을 사용한다.

- `base_branch = "main"`
- `worktree_root = "../_worktrees"`
- `task_dir = ".planning/tasks"`
- `branch_prefix_feature = "feat"`
- `branch_prefix_issue = "fix"`

예시:

```toml
base_branch = "dev"
worktree_root = "../_worktrees"
task_dir = ".planning/tasks"
branch_prefix_feature = "feat"
branch_prefix_issue = "fix"

[commands]
lint = "echo lint-ok"
test = "python -m unittest discover -s tests -v"

[verify]
default = ["lint"]
feature = ["lint", "test"]
issue = ["lint"]
```

`new`는 base branch를 다음 순서로 찾는다.

1. `<base_branch>`
2. `refs/heads/<base_branch>`
3. `origin/<base_branch>`
4. `refs/remotes/origin/<base_branch>`

## Verify 문서 규칙

feature task는 최소한 아래가 채워져야 verify가 audit 단계로 진행된다.

- `BRIEF.md`의 problem
- `BRIEF.md`의 desired outcome
- `BRIEF.md`의 acceptance criteria
- `PLAN.md`의 normal / edge / exception case
- `PLAN.md`의 verification mapping

issue task는 최소한 아래가 채워져야 verify가 audit 단계로 진행된다.

- `BRIEF.md`의 symptom / expected behavior
- `REPRO.md`의 repro steps / expected result / regression target
- `FIX_PLAN.md`의 normal / edge / exception case
- `FIX_PLAN.md`의 verification mapping

## 테스트

전체 테스트:

```bash
uv run python -m unittest discover -s tests -v
```

현재 테스트는 다음을 포함한다.

- feature / issue verify fixture
- close gate fixture
- 실제 branch/worktree 생성
- task 생성 rollback
- agent register/update/run/status
- Codex wrapper 기본 command 구성
- conversation inbox 처리와 daemon dispatch

## 현재 한계

- daemon은 1차 구현이라 단일 프로세스 순차 처리다.
- Slack, GitHub, Jira 같은 외부 이벤트 소스는 아직 연결하지 않았다.
- Claude 기본 자동 실행 wrapper는 아직 없다.
- 이벤트 deduplication이나 retry policy는 아직 단순하다.
- 대화 내용을 더 정교하게 spec으로 materialize하는 LLM orchestration은 아직 없다.
