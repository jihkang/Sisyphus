from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.artifact_snapshot import materialize_feature_task_artifact_snapshot
from sisyphus.audit import run_verify
from sisyphus.cli import build_parser, handle_context_build, handle_index_rebuild, handle_search
from sisyphus.config import load_config
from sisyphus.codex_prompt import build_codex_prompt
from sisyphus.context_pack import (
    EXECUTION_CONTEXT_PACK_PURPOSE,
    build_and_persist_context_pack,
    build_context_pack,
    build_task_execution_context_pack,
    read_context_pack,
)
from sisyphus.mcp_core import SisyphusMcpCoreService
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.retrieval import retrieve_documents
from sisyphus.search_document import project_task_search_documents
from sisyphus.search_index import (
    DEFAULT_SEARCH_INDEX_PATH,
    SearchIndexError,
    read_search_index,
    rebuild_search_index,
)
from sisyphus.state import create_task_record, load_task_record
from sisyphus.templates import materialize_task_templates


class SearchContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "\n".join(
                [
                    'base_branch = "main"',
                    'worktree_root = "../_worktrees"',
                    'task_dir = ".planning/tasks"',
                    'branch_prefix_feature = "feat"',
                    'branch_prefix_issue = "fix"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_search_documents_project_docs_snapshot_and_verification_claims(self) -> None:
        task = self._verified_feature_task("search-docs")

        documents = project_task_search_documents(task, self.repo_root / task["task_dir"])
        doc_keys = {document.doc_key for document in documents}
        source_types = {document.source_type for document in documents}

        self.assertIn("brief", doc_keys)
        self.assertIn("plan", doc_keys)
        self.assertIn("verify", doc_keys)
        self.assertIn("log", doc_keys)
        self.assertIn("artifact_snapshot", source_types)
        self.assertIn("verification_claim", source_types)
        self.assertTrue(all(document.fingerprint.startswith("sha256:") for document in documents))

    def test_index_rebuild_is_deterministic_and_retrieval_ranks_evidence(self) -> None:
        self._verified_feature_task("retrieval-ranking")

        first = rebuild_search_index(self.repo_root, self.config)
        second = rebuild_search_index(self.repo_root, self.config)
        documents = read_search_index(self.repo_root)
        results = retrieve_documents("verification evidence projection", documents, limit=3)

        self.assertGreater(first.document_count, 0)
        self.assertTrue(first.changed)
        self.assertFalse(second.changed)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].rank, 1)
        self.assertGreater(results[0].score, 0)
        self.assertIn(results[0].document.source_type, {"task_doc", "artifact_snapshot", "verification_claim"})
        self.assertTrue(results[0].excerpt)

    def test_context_pack_build_rebuilds_missing_index_and_persists_stable_fingerprint(self) -> None:
        self._verified_feature_task("context-pack")

        pack, path = build_and_persist_context_pack(
            self.repo_root,
            self.config,
            query="artifact projection verification evidence",
            limit=4,
        )
        rebuilt_pack = build_context_pack(
            self.repo_root,
            self.config,
            query="artifact projection verification evidence",
            limit=4,
        )

        self.assertTrue((self.repo_root / DEFAULT_SEARCH_INDEX_PATH).is_file())
        self.assertTrue(path.is_file())
        self.assertEqual(pack["fingerprint"], rebuilt_pack["fingerprint"])
        self.assertEqual(pack["pack_id"], rebuilt_pack["pack_id"])
        self.assertGreater(pack["result_count"], 0)
        self.assertIn("source_ref", pack["items"][0])

    def test_task_execution_context_pack_excludes_current_task(self) -> None:
        prior = self._verified_feature_task("prior-context-evidence")
        current = self._new_feature_task("current-workflow-input")
        self._fill_feature_docs(current)
        docs = self._load_task_docs(current)

        pack, path = build_task_execution_context_pack(
            self.repo_root,
            self.config,
            task=current,
            docs=docs,
            limit=5,
        )

        self.assertTrue(path.is_file())
        self.assertEqual(pack["purpose"], EXECUTION_CONTEXT_PACK_PURPOSE)
        self.assertEqual(pack["source_task_id"], current["id"])
        self.assertIn(current["id"], pack["excluded_task_ids"])
        self.assertGreater(pack["index_document_count"], pack["candidate_document_count"])
        self.assertGreater(pack["result_count"], 0)
        self.assertTrue(all(item.get("task_id") != current["id"] for item in pack["items"]))
        self.assertTrue(any(item.get("task_id") == prior["id"] for item in pack["items"]))

    def test_codex_prompt_includes_context_pack_from_prior_evidence(self) -> None:
        prior = self._verified_feature_task("prompt-prior-evidence")
        current = self._new_feature_task("prompt-current-workflow")
        self._fill_feature_docs(current)

        prompt = build_codex_prompt(
            repo_root=self.repo_root,
            config=self.config,
            task_id=current["id"],
        )

        self.assertIsNotNone(prompt.context_pack)
        self.assertIsNotNone(prompt.context_pack_path)
        assert prompt.context_pack is not None
        assert prompt.context_pack_path is not None
        self.assertTrue(prompt.context_pack_path.is_file())
        self.assertIn("## ContextPack", prompt.prompt)
        self.assertIn("Use this as supporting evidence only", prompt.prompt)
        self.assertIn(f"- Source Task ID: `{current['id']}`", prompt.prompt)
        self.assertIn(prior["id"], prompt.prompt)
        self.assertIn(current["id"], prompt.context_pack["excluded_task_ids"])
        self.assertTrue(all(item.get("task_id") != current["id"] for item in prompt.context_pack["items"]))

    def test_codex_prompt_allows_empty_context_pack_when_only_current_task_matches(self) -> None:
        current = self._new_feature_task("prompt-empty-context")
        self._fill_feature_docs(current)

        prompt = build_codex_prompt(
            repo_root=self.repo_root,
            config=self.config,
            task_id=current["id"],
        )

        self.assertIsNotNone(prompt.context_pack)
        assert prompt.context_pack is not None
        self.assertEqual(prompt.context_pack["result_count"], 0)
        self.assertIn("No ContextPack results selected.", prompt.prompt)

    def test_codex_prompt_rebuilds_missing_index_for_context_pack(self) -> None:
        current = self._new_feature_task("prompt-rebuilds-index")
        self._fill_feature_docs(current)
        index_path = self.repo_root / DEFAULT_SEARCH_INDEX_PATH
        self.assertFalse(index_path.exists())

        prompt = build_codex_prompt(
            repo_root=self.repo_root,
            config=self.config,
            task_id=current["id"],
        )

        self.assertTrue(index_path.is_file())
        self.assertIsNotNone(prompt.context_pack_path)

    def test_codex_prompt_surfaces_malformed_index(self) -> None:
        current = self._new_feature_task("prompt-malformed-index")
        self._fill_feature_docs(current)
        index_path = self.repo_root / DEFAULT_SEARCH_INDEX_PATH
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("{not-json}\n", encoding="utf-8")

        with self.assertRaisesRegex(SearchIndexError, "malformed search index JSONL"):
            build_codex_prompt(
                repo_root=self.repo_root,
                config=self.config,
                task_id=current["id"],
            )

    def test_persisted_snapshot_is_indexed_when_current_docs_are_unavailable(self) -> None:
        task = self._verified_feature_task("stale-snapshot-evidence")
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").unlink()

        documents = project_task_search_documents(task, task_dir)
        snapshots = [document for document in documents if document.source_type == "artifact_snapshot"]

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].freshness_status, "unavailable")
        self.assertIn("snapshot_status", snapshots[0].metadata)

    def test_malformed_index_surfaces_actionable_error(self) -> None:
        index_path = self.repo_root / DEFAULT_SEARCH_INDEX_PATH
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("{not-json}\n", encoding="utf-8")

        with self.assertRaisesRegex(SearchIndexError, "malformed search index JSONL"):
            read_search_index(self.repo_root)

    def test_invalid_context_pack_schema_fails_loudly(self) -> None:
        pack_path = self.repo_root / ".planning" / "context-packs" / "context-pack-invalid.json"
        pack_path.parent.mkdir(parents=True, exist_ok=True)
        pack_path.write_text(json.dumps({"schema_version": "sisyphus.context_pack.v0"}) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "context pack schema_version"):
            read_context_pack(self.repo_root, "context-pack-invalid")

    def test_cli_commands_parse_and_execute(self) -> None:
        self._verified_feature_task("cli-search")
        parser = build_parser()

        index_args = parser.parse_args(["--repo", str(self.repo_root), "index", "rebuild", "--json"])
        search_args = parser.parse_args(["--repo", str(self.repo_root), "search", "projection evidence", "--limit", "2"])
        context_args = parser.parse_args(
            ["--repo", str(self.repo_root), "context", "build", "projection evidence", "--limit", "2", "--json"]
        )

        self.assertEqual(index_args.command, "index")
        self.assertEqual(index_args.index_command, "rebuild")
        self.assertEqual(search_args.command, "search")
        self.assertEqual(context_args.context_command, "build")

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(handle_index_rebuild(as_json=True, repo_root=self.repo_root), 0)
        self.assertIn("document_count", stdout.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(handle_search("projection evidence", limit=2, as_json=False, repo_root=self.repo_root), 0)
        self.assertIn("score=", stdout.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(
                handle_context_build(
                    "projection evidence",
                    limit=2,
                    max_excerpt_chars=240,
                    as_json=True,
                    repo_root=self.repo_root,
                ),
                0,
            )
        payload = json.loads(stdout.getvalue())
        self.assertIn("pack_path", payload)
        self.assertGreater(payload["context_pack"]["result_count"], 0)

    def test_mcp_search_and_context_surfaces(self) -> None:
        self._verified_feature_task("mcp-search")
        core = SisyphusMcpCoreService(self.repo_root)

        rebuild = core.call_tool("sisyphus.search_index_rebuild", {})
        search = core.call_tool("sisyphus.search", {"query": "projection evidence", "limit": 2})
        context = core.call_tool("sisyphus.context_build", {"query": "projection evidence", "limit": 2})
        status = core.read_resource("repo://search/status")
        pack_id = context["context_pack"]["pack_id"]
        persisted = core.read_resource(f"context://{pack_id}")

        self.assertGreater(rebuild["document_count"], 0)
        self.assertGreater(search["result_count"], 0)
        self.assertEqual(status["status"], "ready")
        self.assertEqual(persisted["pack_id"], pack_id)

    def _verified_feature_task(self, slug: str) -> dict:
        task = self._new_feature_task(slug)
        self._fill_feature_docs(task)
        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="tester",
            notes="approved",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="tester",
            notes="frozen",
        )
        run_verify(self.repo_root, self.config, task["id"])
        materialize_feature_task_artifact_snapshot(self.repo_root, self.config, task["id"])
        task, _ = load_task_record(repo_root=self.repo_root, task_dir_name=self.config.task_dir, task_id=task["id"])
        return task

    def _new_feature_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def _load_task_docs(self, task: dict) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        task_dir = self.repo_root / task["task_dir"]
        task_dir_relative = Path(str(task["task_dir"]))
        for key, relative_path in task.get("docs", {}).items():
            if not relative_path:
                continue
            path = task_dir / relative_path
            if not path.exists():
                continue
            display_path = (task_dir_relative / relative_path).as_posix()
            docs.append((f"{key.upper()} ({display_path})", path.read_text(encoding="utf-8")))
        return docs

    def _fill_feature_docs(self, task: dict) -> None:
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Task",
                    "",
                    f"- Task ID: `{task['id']}`",
                    "",
                    "## Problem",
                    "",
                    "- Need artifact projection evidence to be searchable.",
                    "",
                    "## Desired Outcome",
                    "",
                    "- Retrieval finds projection and verification context.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] SearchDocument projection includes task docs",
                    "- [x] Artifact evidence is represented",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "",
                    "## Implementation Plan",
                    "",
                    "1. Build artifact projection.",
                    "2. Record verification evidence.",
                    "",
                    "## Risks",
                    "",
                    "- Retrieval ranking could be unstable.",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Projection evidence is searchable",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Missing optional evidence is tolerated",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Malformed evidence fails clearly",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Projection evidence is searchable` -> `unit_test`",
                    "- `Missing optional evidence is tolerated` -> `unit_test`",
                    "- `Malformed evidence fails clearly` -> `unit_test`",
                    "",
                    "## External LLM Review",
                    "",
                    "- Required: `no`",
                    "- Provider: `n/a`",
                    "- Purpose: `n/a`",
                    "- Trigger: `n/a`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "LOG.md").write_text("# Log\n\n## Timeline\n\n- Projection evidence recorded\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
