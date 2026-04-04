from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from taskflow.provider_wrapper import run_provider_wrapper


if __name__ == "__main__":
    raise SystemExit(run_provider_wrapper("codex", sys.argv[1:]))
