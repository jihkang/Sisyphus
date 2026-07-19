from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sisyphus.application.search.models import SearchDocument
from sisyphus.infra.search import DEFAULT_SEARCH_INDEX_PATH, RepositorySearchIndex


class SearchInfrastructureTests(unittest.TestCase):
    def test_existing_index_reads_and_status_do_not_load_repository_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            document = SearchDocument(
                document_id="searchdoc:task://TF-1/brief",
                source_type="task_doc",
                source_ref="task://TF-1/brief",
                title="existing index",
                content="existing searchable evidence",
                task_id="TF-1",
            )
            index_path = repo_root / DEFAULT_SEARCH_INDEX_PATH
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                json.dumps(document.to_dict(), separators=(",", ":"), sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            adapter = RepositorySearchIndex(
                repo_root,
                config_loader=lambda _: self.fail(
                    "reading an existing index must not load repository config"
                ),
            )

            self.assertEqual(adapter.read(), (document,))
            self.assertEqual(adapter.status()["status"], "ready")


if __name__ == "__main__":
    unittest.main()
