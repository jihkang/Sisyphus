from __future__ import annotations

from pathlib import Path
import subprocess


def detect_repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        current = start.resolve()
        for candidate in (current, *current.parents):
            if (candidate / ".taskflow.toml").exists():
                return candidate
            if (candidate / "pyproject.toml").exists():
                return candidate
        return current
