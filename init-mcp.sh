#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$ROOT_DIR"
SERVER_NAME="sisyphus"
ENABLE_CODEX=1
ENABLE_CLAUDE=1
DRY_RUN=0
MCP_DEBUG_LOG="/tmp/sisyphus-mcp-debug.log"

usage() {
  cat <<'EOF'
Initialize Sisyphus MCP registrations for Codex and Claude.

This script:
- registers a global stdio MCP server in Codex
- writes a project-local .mcp.json for Claude Code

Usage:
  ./init-mcp.sh [options]

Options:
  --repo PATH       Repository root that Sisyphus should manage. Default: this repo.
  --name NAME       MCP server name to register. Default: sisyphus
  --codex-only      Register only in Codex
  --claude-only     Register only in Claude
  --dry-run         Print commands without executing them
  -h, --help        Show this help

Environment overrides:
  CODEX_BIN         Codex CLI path or command name
EOF
}

require_option_value() {
  local option_name="$1"
  local option_value="${2:-}"
  if [[ -z "$option_value" || "$option_value" == -* ]]; then
    echo "Missing value for $option_name" >&2
    exit 1
  fi
}

print_command() {
  local quoted=()
  local arg
  for arg in "$@"; do
    quoted+=("$(printf '%q' "$arg")")
  done
  printf '%s\n' "${quoted[*]}"
}

resolve_repo_root() {
  if [[ ! -d "$REPO_ROOT" ]]; then
    echo "Repository root does not exist: $REPO_ROOT" >&2
    exit 1
  fi
  REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
}

resolve_python_bin() {
  local candidate="$ROOT_DIR/.venv/bin/python"
  if [[ ! -x "$candidate" ]]; then
    echo "Missing Python at $candidate. Run 'uv sync' from $ROOT_DIR first." >&2
    exit 1
  fi
  printf '%s' "$candidate"
}

resolve_codex_bin() {
  if [[ -n "${CODEX_BIN:-}" ]]; then
    if command -v "$CODEX_BIN" >/dev/null 2>&1; then
      command -v "$CODEX_BIN"
      return 0
    fi
    if [[ -x "$CODEX_BIN" ]]; then
      printf '%s' "$CODEX_BIN"
      return 0
    fi
    echo "CODEX_BIN is set but not executable: $CODEX_BIN" >&2
    return 1
  fi
  command -v codex >/dev/null 2>&1 || return 1
  command -v codex
}

register_codex() {
  local codex_bin="$1"
  local python_bin="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    print_command "$codex_bin" mcp remove "$SERVER_NAME"
    print_command \
      "$codex_bin" mcp add "$SERVER_NAME" \
      --env "SISYPHUS_REPO_ROOT=$REPO_ROOT" \
      --env "SISYPHUS_MCP_DEBUG_LOG=$MCP_DEBUG_LOG" \
      -- \
      "$python_bin" -m sisyphus.mcp_server
    return 0
  fi

  "$codex_bin" mcp remove "$SERVER_NAME" >/dev/null 2>&1 || true
  "$codex_bin" mcp add "$SERVER_NAME" \
    --env "SISYPHUS_REPO_ROOT=$REPO_ROOT" \
    --env "SISYPHUS_MCP_DEBUG_LOG=$MCP_DEBUG_LOG" \
    -- \
    "$python_bin" -m sisyphus.mcp_server
}

print_claude_project_config() {
  local python_bin="$2"
  "$python_bin" - "$1" "$SERVER_NAME" "$python_bin" "$REPO_ROOT" "$MCP_DEBUG_LOG" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
name = sys.argv[2]
command = sys.argv[3]
repo_root = sys.argv[4]
debug_log = sys.argv[5]

server_config = {
    "command": command,
    "args": ["-m", "sisyphus.mcp_server"],
    "env": {
        "SISYPHUS_REPO_ROOT": repo_root,
        "SISYPHUS_MCP_DEBUG_LOG": debug_log,
    },
}

data = {}
if path.exists():
    raw = path.read_text(encoding="utf-8")
    if raw.strip():
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise SystemExit(f"{path} must contain a JSON object")

mcp_servers = data.get("mcpServers")
if mcp_servers is None:
    mcp_servers = {}
elif not isinstance(mcp_servers, dict):
    raise SystemExit(f"{path} has a non-object mcpServers value")

mcp_servers[name] = server_config
data["mcpServers"] = mcp_servers
print(json.dumps(data, indent=2))
PY
}

write_claude_project_config() {
  local python_bin="$1"
  local mcp_config_path="$REPO_ROOT/.mcp.json"
  local config_dir tmp_config_path

  config_dir="$(dirname "$mcp_config_path")"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'Would update %s with:\n' "$mcp_config_path"
    print_claude_project_config "$mcp_config_path" "$python_bin"
    return 0
  fi

  tmp_config_path="$(mktemp "$config_dir/.mcp.json.XXXXXX")"
  print_claude_project_config "$mcp_config_path" "$python_bin" >"$tmp_config_path"
  mv "$tmp_config_path" "$mcp_config_path"
  echo "Wrote Claude MCP config: $mcp_config_path"
}

exclude_claude_project_config() {
  local exclude_path="$REPO_ROOT/.git/info/exclude"

  if [[ ! -f "$exclude_path" ]]; then
    return 0
  fi

  if rg -Fx -- ".mcp.json" "$exclude_path" >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'Would append .mcp.json to %s\n' "$exclude_path"
    return 0
  fi

  printf '\n.mcp.json\n' >>"$exclude_path"
  echo "Updated git exclude: $exclude_path"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      require_option_value "$1" "${2:-}"
      REPO_ROOT="$(cd "$2" && pwd)"
      shift 2
      ;;
    --name)
      require_option_value "$1" "${2:-}"
      SERVER_NAME="$2"
      shift 2
      ;;
    --codex-only)
      ENABLE_CODEX=1
      ENABLE_CLAUDE=0
      shift
      ;;
    --claude-only)
      ENABLE_CODEX=0
      ENABLE_CLAUDE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

resolve_repo_root
PYTHON_BIN="$(resolve_python_bin)"

if [[ "$ENABLE_CODEX" -eq 1 ]]; then
  if CODEX_BIN_RESOLVED="$(resolve_codex_bin)"; then
    echo "Registering Codex MCP: $SERVER_NAME"
    register_codex "$CODEX_BIN_RESOLVED" "$PYTHON_BIN"
  else
    echo "Skipping Codex registration: codex CLI not found" >&2
  fi
fi

if [[ "$ENABLE_CLAUDE" -eq 1 ]]; then
  echo "Writing Claude MCP config: $SERVER_NAME"
  write_claude_project_config "$PYTHON_BIN"
  exclude_claude_project_config
fi

echo "Done."
