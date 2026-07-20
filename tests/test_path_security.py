from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.discord_bot import _build_discord_client_class, run_discord_bot
from sisyphus.gitops import (
    GitOperationError,
    copy_relative_path,
    list_dirty_paths,
    push_revision,
    remove_relative_path,
)
from sisyphus.infra.search import RepositoryContextPackStore
from sisyphus.search_index import resolve_search_index_path
from sisyphus.shared.paths import PathBoundaryError, contained_path


class _FakeDiscordBaseClient:
    def __init__(self, **kwargs) -> None:
        self.user = None


class _FakeDiscord:
    Client = _FakeDiscordBaseClient


class PathSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.repo_root = self.base / "repo"
        self.source_root = self.base / "source"
        self.target_root = self.base / "target"
        self.outside_root = self.base / "outside"
        for path in (self.repo_root, self.source_root, self.target_root, self.outside_root):
            path.mkdir()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_contained_path_accepts_children_and_rejects_escape_forms(self) -> None:
        child = self.repo_root / "nested" / "file.txt"

        self.assertEqual(contained_path(self.repo_root, "nested/file.txt"), child)
        self.assertEqual(contained_path(self.repo_root, child), child)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            contained_path(self.repo_root, "../outside/file.txt")
        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            contained_path(self.repo_root, self.outside_root / "file.txt")
        with self.assertRaisesRegex(PathBoundaryError, "must be relative"):
            contained_path(self.repo_root, child, require_relative=True)
        with self.assertRaisesRegex(PathBoundaryError, "must identify a child"):
            contained_path(self.repo_root, ".", require_relative=True)

    def test_contained_path_rejects_symlink_escape(self) -> None:
        escape = self.repo_root / "escape"
        self._symlink_directory(escape, self.outside_root)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            contained_path(self.repo_root, "escape/file.txt")

    def test_search_index_path_is_repo_contained(self) -> None:
        relative = Path(".planning") / "search" / "custom.jsonl"
        absolute_inside = self.repo_root / relative

        self.assertEqual(resolve_search_index_path(self.repo_root, relative), absolute_inside)
        self.assertEqual(resolve_search_index_path(self.repo_root, absolute_inside), absolute_inside)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            resolve_search_index_path(self.repo_root, "../outside/index.jsonl")
        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            resolve_search_index_path(self.repo_root, self.outside_root / "index.jsonl")

    def test_context_pack_store_rejects_invalid_ids_and_symlink_escape(self) -> None:
        store = RepositoryContextPackStore(self.repo_root)
        with self.assertRaisesRegex(ValueError, "invalid context pack id"):
            store.write({"pack_id": "../escape"})

        pack_dir = self.repo_root / ".planning" / "context-packs"
        pack_dir.parent.mkdir(parents=True)
        self._symlink_directory(pack_dir, self.outside_root)
        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            store.write({"pack_id": "context-pack-safe-name"})

    def test_copy_and_remove_relative_path_preserve_normal_behavior(self) -> None:
        source = self.source_root / "nested" / "file.txt"
        source.parent.mkdir()
        source.write_text("payload\n", encoding="utf-8")

        copy_relative_path(self.source_root, self.target_root, "nested/file.txt")

        copied = self.target_root / "nested" / "file.txt"
        self.assertEqual(copied.read_text(encoding="utf-8"), "payload\n")

        remove_relative_path(self.target_root, "nested/file.txt")

        self.assertFalse(copied.exists())

    def test_copy_relative_path_rejects_source_and_target_symlink_escape(self) -> None:
        secret = self.outside_root / "secret.txt"
        secret.write_text("secret\n", encoding="utf-8")
        source_escape = self.source_root / "escape"
        self._symlink_directory(source_escape, self.outside_root)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            copy_relative_path(self.source_root, self.target_root, "escape/secret.txt")

        source = self.source_root / "nested" / "file.txt"
        source.parent.mkdir()
        source.write_text("payload\n", encoding="utf-8")
        target_escape = self.target_root / "nested"
        self._symlink_directory(target_escape, self.outside_root)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            copy_relative_path(self.source_root, self.target_root, "nested/file.txt")
        self.assertEqual(secret.read_text(encoding="utf-8"), "secret\n")

    def test_remove_relative_path_rejects_symlink_escape(self) -> None:
        outside_file = self.outside_root / "file.txt"
        outside_file.write_text("keep\n", encoding="utf-8")
        escape = self.target_root / "escape"
        self._symlink_directory(escape, self.outside_root)

        with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
            remove_relative_path(self.target_root, "escape/file.txt")

        self.assertEqual(outside_file.read_text(encoding="utf-8"), "keep\n")

    def test_git_dirty_paths_use_nul_delimited_filenames(self) -> None:
        self._initialize_git_repo()
        newline_path = "line\nbreak.txt"
        (self.repo_root / newline_path).write_text("dirty\n", encoding="utf-8")

        changed, deleted = list_dirty_paths(self.repo_root)

        self.assertIn(newline_path, changed)
        self.assertEqual(deleted, [])

    def test_git_dirty_paths_fail_closed_when_index_is_corrupt(self) -> None:
        self._initialize_git_repo()
        (self.repo_root / ".git" / "index").write_bytes(b"corrupt-index")

        with self.assertRaisesRegex(GitOperationError, "failed to inspect dirty paths"):
            list_dirty_paths(self.repo_root)

    def test_git_dirty_paths_fail_closed_when_git_cannot_start(self) -> None:
        with mock.patch("sisyphus.gitops.subprocess.run", side_effect=OSError("git missing")):
            with self.assertRaisesRegex(GitOperationError, "git missing"):
                list_dirty_paths(self.repo_root)

    def test_push_revision_uses_exact_sha_refspec_instead_of_moving_branch(self) -> None:
        reviewed_sha = "a" * 40
        with mock.patch("sisyphus.gitops._run_git") as run_git:
            push_revision(self.repo_root, "origin", reviewed_sha, "feat/reviewed")

        run_git.assert_called_once_with(
            self.repo_root,
            ["push", "origin", f"{reviewed_sha}:refs/heads/feat/reviewed"],
            error_prefix="failed to push reviewed revision",
        )

    def test_discord_bot_requires_nonempty_allowlist_before_startup(self) -> None:
        with mock.patch("sisyphus.discord_bot._require_discord") as require_discord:
            with self.assertRaisesRegex(RuntimeError, "at least one Discord channel ID"):
                run_discord_bot(
                    self.repo_root,
                    object(),
                    token="secret",
                    poll_interval_seconds=1,
                    allowed_channel_ids=None,
                )

        require_discord.assert_not_called()

    def test_discord_channel_filter_is_default_deny_and_allows_configured_parent(self) -> None:
        client_class = _build_discord_client_class(_FakeDiscord)
        denied_client = client_class(
            intents=object(),
            repo_root=self.repo_root,
            config=object(),
            poll_interval_seconds=1,
            allowed_channel_ids=[],
        )
        channel = SimpleNamespace(id=200, parent=None)

        self.assertFalse(denied_client._is_allowed_channel(channel))

        allowed_client = client_class(
            intents=object(),
            repo_root=self.repo_root,
            config=object(),
            poll_interval_seconds=1,
            allowed_channel_ids=[100],
        )
        thread = SimpleNamespace(id=200, parent=SimpleNamespace(id=100))

        self.assertTrue(allowed_client._is_allowed_channel(thread))
        self.assertFalse(allowed_client._is_allowed_channel(channel))

    def _symlink_directory(self, link: Path, target: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")

    def _initialize_git_repo(self) -> None:
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.repo_root,
            check=True,
        )
        (self.repo_root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )


if __name__ == "__main__":
    unittest.main()
