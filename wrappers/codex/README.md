# Codex Wrapper

로컬 `codex exec`를 tracked worker로 실행하는 thin wrapper다.

## Sisyphus MCP 연결

가장 간단한 방법은 repo root에서 init 스크립트를 실행하는 것이다.

```bash
./init-mcp.sh
./init-mcp.sh --repo /absolute/path/to/your/repository
```

Codex는 stdio MCP 서버를 직접 붙일 수 있다. init 스크립트는 내부적으로 같은 등록을 수행한다.

현재 canonical direct Python launcher는 `sisyphus.mcp_server`다. 레거시 `taskflow.mcp_server`도 호환 경로로는 계속 동작한다.

현재 repo를 대상으로 바로 추가:

```bash
codex mcp add sisyphus --env PYTHONPATH=/absolute/path/to/Sisyphus/src -- /absolute/path/to/Sisyphus/.venv/bin/python -m sisyphus.mcp_server
```

특정 repo를 명시해서 추가:

```bash
codex mcp add sisyphus --env SISYPHUS_REPO_ROOT=/absolute/path/to/your/repository --env SISYPHUS_MCP_DEBUG_LOG=/tmp/sisyphus-mcp-debug.log --env PYTHONPATH=/absolute/path/to/Sisyphus/src -- /absolute/path/to/Sisyphus/.venv/bin/python -m sisyphus.mcp_server
```

로컬 rename이나 패키지 전환 직후에는 `PYTHONPATH`로 repo `src/`를 우선시해야 stale 설치본을 피할 수 있다.

설정 확인:

```bash
codex mcp list
codex mcp get sisyphus
```

직접 설정 파일로 넣고 싶으면 [`mcp-config.toml.example`](./mcp-config.toml.example) 형식을 `~/.codex/config.toml`에 맞게 복사해서 사용하면 된다.

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

`sisyphus daemon`도 내부적으로 같은 wrapper 경로를 사용한다.
