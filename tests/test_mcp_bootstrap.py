from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = PROJECT_ROOT / "scripts" / "run_sisyphus_mcp_server.py"


def _load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("sisyphus_mcp_bootstrap", BOOTSTRAP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load bootstrap module from {BOOTSTRAP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class McpBootstrapTests(unittest.TestCase):
    def test_prepend_repo_src_moves_repo_src_to_front_without_duplication(self) -> None:
        module = _load_bootstrap_module()
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            repo_src = str((repo_root / "src").resolve())
            original_path = sys.path[:]
            try:
                sys.path[:] = ["/tmp/other", repo_src, "/tmp/fallback"]
                module._prepend_repo_src(repo_root)
                self.assertEqual(sys.path[0], repo_src)
                self.assertEqual(sys.path.count(repo_src), 1)
                self.assertEqual(sys.path[1:], ["/tmp/other", "/tmp/fallback"])
            finally:
                sys.path[:] = original_path

    def test_runtime_snapshot_reports_canonical_sisyphus_paths(self) -> None:
        module = _load_bootstrap_module()
        snapshot = module._runtime_snapshot(PROJECT_ROOT)

        self.assertEqual(snapshot["repo_root"], str(PROJECT_ROOT.resolve()))
        self.assertEqual(snapshot["repo_src"], str((PROJECT_ROOT / "src").resolve()))
        self.assertIn("/src/sisyphus/mcp_server.py", snapshot["mcp_server_file"])
        self.assertIn("/src/sisyphus/templates_data", snapshot["template_root"])
        self.assertNotIn("taskflow/templates_data", snapshot["template_root"])


if __name__ == "__main__":
    unittest.main()
