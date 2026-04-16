# MCP Client Setup

This document shows how to connect Sisyphus to Codex and Claude over MCP.

Sisyphus exposes a stdio MCP server through:

```bash
sisyphus-mcp
```

That entrypoint uses the official MCP Python SDK stdio transport.

By default, the server targets the current working directory as the repository root. To pin it to a specific repository, set:

```bash
export SISYPHUS_REPO_ROOT=/absolute/path/to/your/repository
```

## Recommended: `init-mcp.sh`

From the Sisyphus repo root:

```bash
./init-mcp.sh
./init-mcp.sh --repo /absolute/path/to/your/repository
```

That script does two things:

- registers a global Codex stdio MCP server named `sisyphus`
- writes a Claude Code project `.mcp.json` into the managed repository and adds `.mcp.json` to `.git/info/exclude` when possible

## Codex

Codex supports MCP server registration from the CLI.

The preferred direct Python launcher path is `sisyphus.mcp_server`.

The legacy module path `taskflow.mcp_server` remains available as a compatibility alias.

Add Sisyphus for the current repository:

```bash
codex mcp add sisyphus -- /absolute/path/to/Sisyphus/.venv/bin/python -m sisyphus.mcp_server
```

Add Sisyphus for a specific repository:

```bash
codex mcp add sisyphus --env SISYPHUS_REPO_ROOT=/absolute/path/to/your/repository --env SISYPHUS_MCP_DEBUG_LOG=/tmp/sisyphus-mcp-debug.log -- /absolute/path/to/Sisyphus/.venv/bin/python -m sisyphus.mcp_server
```

Inspect the registration:

```bash
codex mcp list
codex mcp get sisyphus
```

If you prefer file-based configuration, use [wrappers/codex/mcp-config.toml.example](../wrappers/codex/mcp-config.toml.example) as a template for `~/.codex/config.toml`.

## Claude

Claude Code supports project-scoped MCP configuration through `.mcp.json`.

As with the Codex examples above, the JSON points at `sisyphus.mcp_server` as the canonical launcher path.

Create `.mcp.json` in the target repository root:

```bash
cat > .mcp.json <<'EOF'
{
  "mcpServers": {
    "sisyphus": {
      "command": "/absolute/path/to/Sisyphus/.venv/bin/python",
      "args": ["-m", "sisyphus.mcp_server"],
      "env": {
        "SISYPHUS_REPO_ROOT": "/absolute/path/to/your/repository",
        "SISYPHUS_MCP_DEBUG_LOG": "/tmp/sisyphus-mcp-debug.log"
      }
    }
  }
}
EOF
```

If your Claude CLI exposes `claude mcp add-json`, you can also register from a JSON payload directly. Use [wrappers/claude/mcp-server.json.example](../wrappers/claude/mcp-server.json.example) as the payload shape for that path.

Inspect the registration from Claude Code:

```bash
claude mcp get sisyphus
claude mcp list
```

## Recommended Agent Guidance

To make the clients use Sisyphus consistently, add guidance to your repo-level agent instructions. For example:

```text
Use the Sisyphus MCP server for task lifecycle operations before editing task state directly.
Read task://<task-id>/record and task://<task-id>/conformance before continuing work on an existing task.
Use Sisyphus tools for request_task, verify_task, close_task, and plan/spec review transitions.
```

## Available MCP Surface

The Sisyphus MCP server currently exposes these tool groups:

- task creation and lookup
- plan review and spec freeze transitions
- subtask generation
- verify and close
- agent listing
- one-shot daemon processing

It also exposes these resource groups:

- repository task status
- repository-wide conformance board
- operator-focused status board with recent events
- recent event bus envelopes
- MCP schema/reference document
- task record JSON
- task conformance summary
- task docs such as brief, plan, verify, and log
- task agent records
