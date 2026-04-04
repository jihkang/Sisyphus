# Codex Wrapper

로컬 `codex exec`를 tracked worker로 실행하는 thin wrapper다.

기본 실행:

```bash
python wrappers/codex/run.py <task-id> <agent-id> --role worker
```

대화 한 줄로 task 생성과 Codex 실행을 같이 하고 싶으면:

```bash
python wrappers/codex/run.py conversation "에이전트 상태 대시보드를 추가해줘" --agent-id worker-1
```

추가 지시 포함:

```bash
python wrappers/codex/run.py <task-id> <agent-id> --role worker --instruction "focus on failing tests first"
```

Codex 인자 추가:

```bash
python wrappers/codex/run.py <task-id> <agent-id> --provider-arg=--full-auto --provider-arg=--json
```

wrapper는 다음을 자동으로 처리한다.

1. `task.json`과 task 문서를 읽는다.
2. Codex prompt를 구성한다.
3. `codex exec -C <worktree> -`를 실행한다.
4. agent 상태와 heartbeat를 기록한다.
5. stdout 일부를 `last_message_summary`에 반영한다.

`taskflow daemon`도 내부적으로 같은 wrapper 경로를 사용한다.
