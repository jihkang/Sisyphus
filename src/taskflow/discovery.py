from __future__ import annotations

from pathlib import Path
import subprocess

from .config import CONFIG_FILENAMES


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
            for filename in CONFIG_FILENAMES:
                if (candidate / filename).exists():
                    return candidate
            if (candidate / "pyproject.toml").exists():
                return candidate
        return current
