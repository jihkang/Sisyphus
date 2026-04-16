from __future__ import annotations

from taskflow.mcp_server import build_server, main, resolve_mcp_repo_root, run_stdio_server

__all__ = ["build_server", "main", "resolve_mcp_repo_root", "run_stdio_server"]


if __name__ == "__main__":
    raise SystemExit(main())
