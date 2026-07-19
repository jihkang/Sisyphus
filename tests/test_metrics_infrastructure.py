from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sisyphus.infra.metrics import read_metric_entries


class MetricsInfrastructureTests(unittest.TestCase):
    def test_metric_reader_skips_malformed_lines_and_sorts_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"event_id": "later", "timestamp": "2026-07-19T12:01:00Z"}),
                        "{not-json}",
                        json.dumps({"event_id": "earlier", "timestamp": "2026-07-19T12:00:00Z"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            entries = read_metric_entries([path])

        self.assertEqual([entry["event_id"] for entry in entries], ["earlier", "later"])


if __name__ == "__main__":
    unittest.main()
