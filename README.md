# Sisyphus

Sisyphus is a Python work orchestration tool for repository-local planning, artifact projection, obligation execution, verification, promotion, and closeout. It is designed to be installed once and then run inside any target project repository.

Preferred command:

```bash
sisyphus request "Add an agent dashboard"
```

That command creates and manages task state in the current repository:

- `.planning/tasks/...`
- `.planning/inbox/...`
- project worktrees and task branches

Sisyphus itself does not need to live inside the target repository. The important rule is simple: run `sisyphus` from the repo you want to manage, or pass `--repo` explicitly.

## Install

### Requirements

- Python 3.11+
- `uv`
- `git`

### Windows

Use PowerShell:

```powershell
git clone <repo-url>
cd Sisyphus
uv sync
uv run sisyphus status
```

To install it as a reusable command:

```powershell
git clone <repo-url>
cd Sisyphus
uv tool install .
sisyphus status
```

### macOS

Use Terminal:

```bash
git clone <repo-url>
cd Sisyphus
uv sync
uv run sisyphus status
```

To install it as a reusable command:

```bash
git clone <repo-url>
cd Sisyphus
uv tool install .
sisyphus status
```

### Discord Support

Repo-local environment:

```bash
uv sync --extra discord
```

Tool install:

```bash
uv tool install ".[discord]"
```

### Update

If you installed with `uv tool install .`, update from the repo root with:

```bash
uv tool install . --force
```

## Usage Model

The default target repository is the current working directory.

Example:

```bash
cd /path/to/my-product
sisyphus request "Build a voice meeting assistant"
```

That creates task state inside `/path/to/my-product`, not inside the Sisyphus source repository.

If you need to manage a different repository from the current shell location, use `--repo`:

```bash
sisyphus --repo /path/to/my-product request "Build a voice meeting assistant"
```

## Core Commands

Create and run a task:

```bash
sisyphus request "Add an agent dashboard"
```

Create a task but stop before execution:

```bash
sisyphus request "Draft the plan only" --no-run
```

Queue a conversation event without immediately processing it:

```bash
sisyphus ingest conversation "Add an agent dashboard" --no-run
```

Process pending inbox events once:

```bash
sisyphus daemon --once
```

Run the long-lived service loop:

```bash
sisyphus serve
```

Show task and agent status:

```bash
sisyphus status
sisyphus status --agents
sisyphus agents --json
```

Manual lifecycle commands:

```bash
sisyphus plan approve <task-id> --by reviewer
sisyphus plan request-changes <task-id> --by reviewer --notes "split the work more clearly"
sisyphus plan revise <task-id> --by worker --notes "updated the plan"
sisyphus spec freeze <task-id> --by reviewer
sisyphus subtasks generate <task-id>
sisyphus verify <task-id>
sisyphus close <task-id>
```

## Workflow

The operator-facing workflow is:

1. Intake a request.
2. Create a repository-local task workspace.
3. Draft and review the plan.
4. Freeze the spec.
5. Generate subtasks.
6. Run worker execution.
7. Verify results.
8. Close the task.

The orchestration loop can pause in `needs_user_input` when review limits are hit or human guidance is required.

Internally, feature work is also projected into an artifact-governed path:

```text
Feature task record
-> FeatureChangeArtifact projection snapshot
-> FeatureChange evaluation
-> ObligationIntent
-> ProtocolSpec + ObligationSpec + InputContract
-> CompiledObligation queue
-> ExecutionPolicy-backed daemon convergence
-> VerificationClaim / promotion decision
```

The DSL owns what must be read, produced, and verified. Execution policy owns who or what performs the work, such as a local Sisyphus verifier, tool runner, or future agent/provider overlay.

Key persisted artifact outputs currently include:

- `.planning/tasks/<task-id>/artifacts/projection/feature-change.json`
- `.planning/tasks/<task-id>/artifacts/obligations/compiled.json`

## Discord Bot

Set the token and start the bot:

Windows PowerShell:

```powershell
$env:DISCORD_BOT_TOKEN="YOUR_TOKEN"
sisyphus discord-bot --channel-id 123456789012345678
```

macOS:

```bash
export DISCORD_BOT_TOKEN="YOUR_TOKEN"
sisyphus discord-bot --channel-id 123456789012345678
```

By default the bot manages the repository in the current directory. To target a different repository, add `--repo`.

## Python Library

Sisyphus can also be imported directly:

```python
from pathlib import Path
import sisyphus

result = sisyphus.request_task(
    repo_root=Path("/path/to/my-product"),
    message="Build a voice meeting assistant",
    title="Voice Meeting Assistant",
    auto_run=True,
)

print(result.ok)
print(result.task_id)
print(result.task["status"])
print(result.task["workflow_phase"])
```

Useful API entrypoints:

- `sisyphus.queue_conversation(...)`
- `sisyphus.request_task(...)`

## MCP Clients

Sisyphus can be exposed to coding agents over MCP through:

```bash
sisyphus-mcp
```

The MCP entrypoint is backed by the official MCP Python SDK over stdio.

The recommended launcher also sets `PYTHONPATH=/absolute/path/to/Sisyphus/src` so active MCP registrations prefer the current repo source over any stale installed package copy.

Quick start from the Sisyphus repo root:

```bash
./init-mcp.sh
./init-mcp.sh --repo /absolute/path/to/your/repository
```

That script registers Sisyphus in Codex and writes a Claude Code project `.mcp.json` for the managed repository.

Client setup examples for Codex and Claude are documented in [docs/mcp-clients.md](docs/mcp-clients.md).
Repo-level agent guidance for preferring Sisyphus MCP tools and resources lives in [AGENTS.md](AGENTS.md).

## Configuration

Repository-level configuration prefers `.sisyphus.toml`.

Legacy repositories can continue using `.taskflow.toml` as a fallback compatibility filename.

Default values:

```toml
base_branch = "main"
worktree_root = "../_worktrees"
task_dir = ".planning/tasks"
branch_prefix_feature = "feat"
branch_prefix_issue = "fix"
```

Example:

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

## Tests

Run the full suite:

```bash
uv run python -m unittest discover -s tests -v
```

## Notes

- `sisyphus` is the preferred command surface.
- The direct MCP launcher is `python -m sisyphus.mcp_server`.
- For durable local registration, include `PYTHONPATH=/absolute/path/to/Sisyphus/src` in the MCP server environment.
- The package name is currently `taskflow-kit`.
- Project philosophy: see `docs/philosophy.md`.
- LinkedIn weekly summary example: see `docs/linkedin-weekly-main-summary-2026-04-17.md`.
- Phone-first automation proposal: see `docs/mobile-automation-spec.md`.
