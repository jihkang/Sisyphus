# Claude Wrapper

Tracked wrapper for manual Claude-oriented commands.

현재는 기본 Claude 실행 로직은 없고, `--` 뒤 명령을 추적하면서 실행하는 용도입니다.

```bash
python wrappers/claude/run.py <task-id> <agent-id> --role worker -- python -c "print('ok')"
```
