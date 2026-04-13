# Claude Wrapper

Tracked wrapper for manual Claude-oriented commands.

## Sisyphus MCP 연결

가장 간단한 방법은 repo root에서 init 스크립트를 한 번 실행하는 것이다.

```bash
./init-mcp.sh
./init-mcp.sh --repo /absolute/path/to/your/repository
```

이 스크립트는 관리 대상 repo에 Claude Code용 `.mcp.json`을 써 준다.

수동으로 할 경우에는 target repo root에 `.mcp.json`을 두는 방식이 가장 안정적이다.

```json
{
  "mcpServers": {
    "sisyphus": {
      "command": "/absolute/path/to/Sisyphus/.venv/bin/python",
      "args": ["-m", "taskflow.mcp_server"],
      "env": {
        "SISYPHUS_REPO_ROOT": "/absolute/path/to/your/repository",
        "SISYPHUS_MCP_DEBUG_LOG": "/tmp/sisyphus-mcp-debug.log"
      }
    }
  }
}
```

공식 Claude CLI가 `claude mcp add-json`를 지원하는 환경이면, 아래처럼 직접 등록해도 된다.

```bash
claude mcp add-json sisyphus '{
  "type": "stdio",
  "command": "/absolute/path/to/Sisyphus/.venv/bin/python",
  "args": ["-m", "taskflow.mcp_server"],
  "env": {
    "SISYPHUS_REPO_ROOT": "/absolute/path/to/your/repository",
    "SISYPHUS_MCP_DEBUG_LOG": "/tmp/sisyphus-mcp-debug.log"
  }
}'
```

등록 확인:

```bash
claude mcp get sisyphus
claude mcp list
```

직접 CLI payload JSON을 따로 관리하고 싶으면 [`mcp-server.json.example`](./mcp-server.json.example) 형식을 기준으로 사용하면 된다.

현재는 기본 Claude 실행 로직은 없고, `--` 뒤 명령을 추적하면서 실행하는 용도입니다.

```bash
python wrappers/claude/run.py <task-id> <agent-id> --role worker -- python -c "print('ok')"
```
