from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ...shared.paths import event_log_file
from ..events import append_jsonl_text


class JsonlDaemonEventLog:
    def __init__(self, repo_root: Path) -> None:
        self._path = event_log_file(repo_root)

    def append(self, entry: Mapping[str, object]) -> None:
        append_jsonl_text(self._path, json.dumps(dict(entry)))


__all__ = ["JsonlDaemonEventLog"]
