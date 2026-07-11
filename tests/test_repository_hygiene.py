from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "CONTRIBUTING.md",
    PROJECT_ROOT / "RELEASES.md",
    PROJECT_ROOT / "docs" / "architecture.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class RepositoryHygieneTests(unittest.TestCase):
    def test_local_document_links_resolve(self) -> None:
        missing: list[str] = []
        for document in DOCUMENTS:
            content = document.read_text(encoding="utf-8")
            for raw_target in MARKDOWN_LINK.findall(content):
                target = raw_target.split("#", 1)[0].strip()
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(PROJECT_ROOT)} -> {raw_target}")

        self.assertEqual(missing, [])

    def test_architecture_names_current_implementation_boundaries(self) -> None:
        architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertNotIn("src/taskflow", architecture)
        for boundary in ("interfaces", "domain", "infra", "shared", "compat"):
            self.assertIn(boundary, architecture)
        self.assertIn("task://<task-id>/observation", architecture)

    def test_coverage_configuration_is_locked_and_enforced(self) -> None:
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        self.assertIn("coverage==7.15.0", pyproject["dependency-groups"]["dev"])
        self.assertTrue(pyproject["tool"]["coverage"]["run"]["branch"])
        self.assertGreaterEqual(pyproject["tool"]["coverage"]["report"]["fail_under"], 80)

        workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("coverage run -m unittest discover -s tests", workflow)
        self.assertIn("coverage report", workflow)

    def test_mit_license_is_declared_consistently(self) -> None:
        license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 jihkang", license_text)
        self.assertIn("Permission is hereby granted, free of charge", license_text)

        with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)
        self.assertEqual(pyproject["project"]["license"], "MIT")
        self.assertEqual(pyproject["project"]["license-files"], ["LICENSE"])

        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[MIT License](LICENSE)", readme)


if __name__ == "__main__":
    unittest.main()
