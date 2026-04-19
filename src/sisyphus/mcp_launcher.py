from __future__ import annotations

from pathlib import Path


def repo_src_path(repo_root: str | Path) -> str:
    return str(Path(repo_root).resolve() / "src")


def build_mcp_server_env(
    repo_root: str | Path,
    debug_log: str,
    *,
    inherited_pythonpath: str | None = None,
) -> dict[str, str]:
    repo_root_str = str(Path(repo_root).resolve())
    repo_pythonpath = repo_src_path(repo_root_str)
    if inherited_pythonpath:
        pythonpath = f"{repo_pythonpath}:{inherited_pythonpath}"
    else:
        pythonpath = repo_pythonpath
    return {
        "SISYPHUS_REPO_ROOT": repo_root_str,
        "SISYPHUS_MCP_DEBUG_LOG": str(debug_log),
        "PYTHONPATH": pythonpath,
    }


def build_stdio_server_config(
    command: str,
    repo_root: str | Path,
    debug_log: str,
    *,
    inherited_pythonpath: str | None = None,
) -> dict[str, object]:
    return {
        "command": command,
        "args": ["-m", "sisyphus.mcp_server"],
        "env": build_mcp_server_env(
            repo_root,
            debug_log,
            inherited_pythonpath=inherited_pythonpath,
        ),
    }


__all__ = [
    "build_mcp_server_env",
    "build_stdio_server_config",
    "repo_src_path",
]
