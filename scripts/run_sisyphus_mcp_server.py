from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo_root() -> Path:
    explicit = os.environ.get("SISYPHUS_REPO_ROOT")
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[1]


def _prepend_repo_src(repo_root: Path) -> None:
    repo_src = str((repo_root / "src").resolve())
    sys.path[:] = [repo_src, *[entry for entry in sys.path if entry != repo_src]]


def _runtime_snapshot(repo_root: Path) -> dict[str, str]:
    import sisyphus.mcp_server as mcp_server
    import sisyphus.templates as templates

    return {
        "repo_root": str(repo_root),
        "repo_src": str((repo_root / "src").resolve()),
        "mcp_server_file": str(Path(mcp_server.__file__).resolve()),
        "template_root": str(templates.template_root()),
    }


def main() -> int:
    repo_root = _resolve_repo_root()
    _prepend_repo_src(repo_root)
    if os.environ.get("SISYPHUS_MCP_BOOTSTRAP_INSPECT") == "1":
        print(json.dumps(_runtime_snapshot(repo_root), indent=2))
        return 0
    from sisyphus.mcp_server import main as server_main

    return server_main()


if __name__ == "__main__":
    raise SystemExit(main())
