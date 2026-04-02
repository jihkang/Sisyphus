# Sisyphus

Sisyphus는 git worktree 기반의 공용 task lifecycle 유틸리티를 만드는 프로젝트입니다.

목표는 저장소마다 중복되는 작업 흐름을 복사하지 않고, 하나의 공통 CLI로 아래 흐름을 재사용하는 것입니다.

```text
task -> spec -> create -> audit -> next task
  |<------------------------------------| no
```

핵심 아이디어는 다음과 같습니다.

- task 상태는 각 소비 저장소의 `.planning/tasks/...`에 둡니다.
- 저장소별 정책은 `.taskflow.toml`에 둡니다.
- 공통 메커니즘은 `taskflow-kit`가 담당합니다.
- `verify`는 바로 실행 검증으로 가지 않고, 먼저 spec completeness를 확인합니다.

## 현재 포함된 내용

- Python 기반 `taskflow` CLI 초안
- feature / issue task 템플릿
- `task.json` 상태 모델
- spec-first `verify`
- `status`, `close` 최소 동작
- golden fixture 기반 테스트

## 현재 지원하는 명령

- `taskflow new feature <slug>`
- `taskflow new issue <slug>`
- `taskflow verify <task-id>`
- `taskflow close <task-id>`
- `taskflow status`

## 디렉터리 구조

```text
taskflow-kit/
  pyproject.toml
  src/taskflow/
  templates/
    feature/
    issue/
  tests/
    fixtures/
```

## 어떻게 사용하나

### 1. 설치 없이 로컬에서 바로 실행

프로젝트 루트에서 아래처럼 실행할 수 있습니다.

```bash
cd taskflow-kit/src
python3 -m taskflow.cli status
```

### 2. 새 feature task 만들기

```bash
cd taskflow-kit/src
python3 -m taskflow.cli new feature sample-task
```

생성되면 아래 파일들이 생깁니다.

- `.planning/tasks/<task-id>/task.json`
- `BRIEF.md`
- `PLAN.md`
- `VERIFY.md`
- `LOG.md`

### 3. spec 먼저 채우기

feature는 주로 아래를 먼저 채워야 합니다.

- `BRIEF.md`의 problem / desired outcome / acceptance criteria
- `PLAN.md`의 normal / edge / exception case
- `PLAN.md`의 verification mapping
- `PLAN.md`의 external LLM review policy

issue는 아래가 더 중요합니다.

- `REPRO.md`
- `FIX_PLAN.md`
- regression target

## verify는 어떻게 동작하나

`verify`는 두 단계로 동작합니다.

1. spec completeness 검사
2. spec이 충분할 때만 audit 실행

즉 문서가 비어 있거나 테스트 전략이 미완성인 상태에서는 command verify보다 먼저 spec gate가 걸립니다.

실행 예시:

```bash
cd taskflow-kit/src
python3 -m taskflow.cli verify TF-20260402-feature-sample-task
```

검증 결과는 아래에 반영됩니다.

- `.planning/tasks/<task-id>/task.json`
- `.planning/tasks/<task-id>/VERIFY.md`

## status는 언제 쓰나

현재 열린 task, 막힌 task, 검증 완료된 task 상태를 빠르게 보는 용도입니다.

```bash
cd taskflow-kit/src
python3 -m taskflow.cli status
python3 -m taskflow.cli status --blocked
python3 -m taskflow.cli status --json
```

## close는 언제 되나

`close`는 아래 조건을 만족해야 합니다.

- `verify_status = passed`
- unresolved gate 없음
- dirty worktree가 없거나 `--allow-dirty` 사용

예시:

```bash
cd taskflow-kit/src
python3 -m taskflow.cli close <task-id>
```

## 테스트 실행

현재 테스트는 `unittest` 기반입니다.

```bash
cd taskflow-kit
python3 -m unittest discover -s tests -v
```

현재 포함된 테스트 범위:

- feature spec incomplete / complete
- issue spec incomplete / complete
- close requires verify
- close allows verified task

## 현재 한계

아직 아래는 진행 중입니다.

- 실제 `git worktree add/remove`
- branch 생성 및 checkout
- Jira / 대화 기반 spec materialization
- external LLM 실제 실행 연동
- dirty worktree, audit limit 등의 fixture 확장

## 문서

설계 문서는 `../docs/` 아래에 정리되어 있습니다.

- `taskflow-review.md`
- `taskflow-verify-spec.md`
- `taskflow-test-spec.md`
- `taskflow-todo.md`
