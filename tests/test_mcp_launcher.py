from __future__ import annotations

from pathlib import Path
import unittest

from sisyphus.mcp_launcher import build_mcp_server_env, build_stdio_server_config, repo_src_path
from sisyphus.templates import template_root


class McpLauncherTests(unittest.TestCase):
    def test_repo_src_path_uses_sisyphus_repo_src_directory(self) -> None:
        repo_root = Path("/tmp/example-repo")
        self.assertEqual(repo_src_path(repo_root), str(repo_root.resolve() / "src"))

    def test_build_mcp_server_env_prefers_repo_src_before_inherited_pythonpath(self) -> None:
        env = build_mcp_server_env(
            "/tmp/example-repo",
            "/tmp/sisyphus-mcp-debug.log",
            inherited_pythonpath="/tmp/site-packages",
        )

        self.assertEqual(env["SISYPHUS_REPO_ROOT"], str(Path("/tmp/example-repo").resolve()))
        self.assertEqual(env["SISYPHUS_MCP_DEBUG_LOG"], "/tmp/sisyphus-mcp-debug.log")
        self.assertEqual(
            env["PYTHONPATH"],
            f"{Path('/tmp/example-repo').resolve() / 'src'}:/tmp/site-packages",
        )

    def test_build_stdio_server_config_uses_sisyphus_launcher_and_env(self) -> None:
        config = build_stdio_server_config(
            "/tmp/sisyphus-venv/bin/python",
            "/tmp/example-repo",
            "/tmp/sisyphus-mcp-debug.log",
        )

        self.assertEqual(config["command"], "/tmp/sisyphus-venv/bin/python")
        self.assertEqual(config["args"], ["-m", "sisyphus.mcp_server"])
        env = config["env"]
        self.assertEqual(env["SISYPHUS_REPO_ROOT"], str(Path("/tmp/example-repo").resolve()))
        self.assertEqual(env["PYTHONPATH"], str(Path("/tmp/example-repo").resolve() / "src"))

    def test_template_root_points_at_sisyphus_package_data_not_taskflow(self) -> None:
        root = template_root()
        feature_brief = root.joinpath("feature", "BRIEF.md")

        self.assertTrue(feature_brief.is_file())
        self.assertIn("sisyphus", str(root))
        self.assertNotIn("taskflow/templates_data", str(root))


if __name__ == "__main__":
    unittest.main()
