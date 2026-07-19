from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import unittest

from sisyphus.application.search.models import SearchDocument, SearchIndexRebuildResult
from sisyphus.application.use_cases.search import (
    EXECUTION_CONTEXT_PACK_PURPOSE,
    SearchService,
)


class FakeSearchIndex:
    def __init__(
        self,
        documents: tuple[SearchDocument, ...],
        *,
        available: bool = True,
    ) -> None:
        self.documents = documents
        self.available = available
        self.read_calls = 0
        self.rebuild_calls = 0

    def rebuild(self) -> SearchIndexRebuildResult:
        self.rebuild_calls += 1
        self.available = True
        return SearchIndexRebuildResult(
            index_path=Path("/repo/.planning/search/index.jsonl"),
            document_count=len(self.documents),
            changed=True,
        )

    def read(self) -> tuple[SearchDocument, ...]:
        self.read_calls += 1
        if not self.available:
            raise FileNotFoundError("search index not found")
        return self.documents

    def status(self) -> dict[str, object]:
        return {
            "status": "ready" if self.available else "missing",
            "document_count": len(self.documents) if self.available else 0,
        }


class FakeContextPackStore:
    def __init__(self) -> None:
        self.packs: dict[str, dict[str, object]] = {}

    def write(self, pack: Mapping[str, object]) -> Path:
        pack_id = str(pack["pack_id"])
        self.packs[pack_id] = dict(pack)
        return Path(f"/repo/.planning/context-packs/{pack_id}.json")

    def read(self, pack_id: str) -> dict[str, object]:
        return dict(self.packs[pack_id])


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class SearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.current = SearchDocument(
            document_id="searchdoc:task://TF-CURRENT/plan",
            source_type="task_doc",
            source_ref="task://TF-CURRENT/plan",
            title="current projection plan",
            content="projection evidence for the current task",
            task_id="TF-CURRENT",
        )
        self.prior = SearchDocument(
            document_id="searchdoc:task://TF-PRIOR/verify",
            source_type="verification_claim",
            source_ref="task://TF-PRIOR/verification-claims#claim-1",
            title="prior projection verification",
            content="measured projection evidence from a completed task",
            task_id="TF-PRIOR",
        )

    def _service(
        self,
        *,
        available: bool = True,
    ) -> tuple[SearchService, FakeSearchIndex, FakeContextPackStore]:
        index = FakeSearchIndex((self.current, self.prior), available=available)
        packs = FakeContextPackStore()
        return SearchService(index=index, packs=packs, clock=FixedClock()), index, packs

    def test_search_rebuilds_a_missing_index_once_when_requested(self) -> None:
        service, index, _ = self._service(available=False)

        results = service.search(
            "projection evidence",
            limit=2,
            rebuild_if_missing=True,
        )

        self.assertEqual(index.rebuild_calls, 1)
        self.assertEqual(index.read_calls, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].document, self.prior)

    def test_search_preserves_missing_index_failure_without_rebuild_permission(self) -> None:
        service, index, _ = self._service(available=False)

        with self.assertRaisesRegex(FileNotFoundError, "search index not found"):
            service.search("projection", limit=1)

        self.assertEqual(index.rebuild_calls, 0)
        self.assertEqual(index.read_calls, 1)

    def test_context_pack_excludes_source_task_and_persists_stable_fingerprint(self) -> None:
        service, _, packs = self._service()

        pack, path = service.build_and_persist_context_pack(
            query="projection evidence",
            limit=5,
            exclude_task_ids=("TF-CURRENT",),
            source_task_id="TF-CURRENT",
            purpose=EXECUTION_CONTEXT_PACK_PURPOSE,
        )
        rebuilt = service.build_context_pack(
            query="projection evidence",
            limit=5,
            exclude_task_ids=["TF-CURRENT"],
            source_task_id="TF-CURRENT",
            purpose=EXECUTION_CONTEXT_PACK_PURPOSE,
        )

        self.assertEqual(pack["built_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(pack["fingerprint"], rebuilt["fingerprint"])
        self.assertEqual(pack["pack_id"], rebuilt["pack_id"])
        self.assertEqual(pack["candidate_document_count"], 1)
        self.assertEqual([item["task_id"] for item in pack["items"]], ["TF-PRIOR"])
        self.assertEqual(path.name, f"{pack['pack_id']}.json")
        self.assertEqual(packs.read(str(pack["pack_id"])), pack)

    def test_task_execution_context_requires_an_id(self) -> None:
        service, _, _ = self._service()

        with self.assertRaisesRegex(ValueError, "requires task id"):
            service.build_task_execution_context_pack(
                task={"slug": "missing-id"},
                docs=[],
            )

    def test_public_search_facades_preserve_canonical_symbol_identity(self) -> None:
        from sisyphus import retrieval, search_document, search_index
        from sisyphus.application.search import models, retrieval as canonical_retrieval
        from sisyphus.infra.search import documents, index

        self.assertIs(retrieval.retrieve_documents, canonical_retrieval.retrieve_documents)
        self.assertIs(search_document.SearchDocument, models.SearchDocument)
        self.assertIs(
            search_document.project_task_search_documents,
            documents.project_task_search_documents,
        )
        self.assertIs(search_index.read_search_index, index.read_search_index)
        self.assertIs(search_index.SearchIndexError, models.SearchIndexError)


if __name__ == "__main__":
    unittest.main()
