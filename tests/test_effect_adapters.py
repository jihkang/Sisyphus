from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.application.results.artifacts import ArtifactRef
from sisyphus.infra.config.loader import load_config
from sisyphus.infra.verification.adapters import FileVerificationDocumentAdapter


class EffectAdapterTests(unittest.TestCase):
    def test_verification_documents_delegate_writes_to_atomic_artifact_store(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            task_dir = repo_root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            adapter = FileVerificationDocumentAdapter(repo_root, load_config(repo_root))

            with mock.patch(
                "sisyphus.infra.artifacts.store.write_text_file"
            ) as write_text_file:
                artifact = adapter.write("TF-1", "VERIFY.md", "verification\n")

            self.assertEqual(artifact, ArtifactRef("VERIFY.md"))
            write_text_file.assert_called_once_with(
                task_dir / "VERIFY.md",
                "verification\n",
            )


if __name__ == "__main__":
    unittest.main()
