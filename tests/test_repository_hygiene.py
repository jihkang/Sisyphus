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
    PROJECT_ROOT / "docs" / "architecture-and-data-pipeline.md",
    PROJECT_ROOT / "docs" / "runtime-relationship-diagrams.md",
    PROJECT_ROOT / "docs" / "clean-architecture-implementation-debt.md",
    PROJECT_ROOT / "docs" / "adr" / "0001-clean-architecture-boundaries.md",
    PROJECT_ROOT / "docs" / "reviews" / "clean-architecture-final-review-2026-07-20.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

CANONICAL_ARCHITECTURE_PATHS = (
    "src/sisyphus/application/use_cases/workflow.py",
    "src/sisyphus/application/use_cases/verification.py",
    "src/sisyphus/application/use_cases/promotion_execution.py",
    "src/sisyphus/application/use_cases/promotion_merge.py",
    "src/sisyphus/application/spec_validation_rules.py",
    "src/sisyphus/composition/repository_requests.py",
    "src/sisyphus/composition/evolution_evaluation.py",
    "src/sisyphus/infra/persistence/task_records.py",
    "src/sisyphus/infra/persistence/record_mapper.py",
    "src/sisyphus/infra/validation/spec_validation.py",
    "src/sisyphus/domain/agent/repository.py",
    "src/sisyphus/domain/task/repository.py",
)


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

    def test_architecture_documents_match_current_implementation(self) -> None:
        architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        pipeline = (PROJECT_ROOT / "docs" / "architecture-and-data-pipeline.md").read_text(
            encoding="utf-8"
        )
        diagrams = (PROJECT_ROOT / "docs" / "runtime-relationship-diagrams.md").read_text(
            encoding="utf-8"
        )
        adr = (PROJECT_ROOT / "docs" / "adr" / "0001-clean-architecture-boundaries.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((architecture, pipeline, diagrams, adr))

        for relative_path in CANONICAL_ARCHITECTURE_PATHS:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())
                self.assertIn(relative_path.removeprefix("src/sisyphus/"), combined)

        for stale_claim in (
            "domain/workflow/service.py",
            "domain/planning/spec_validation.py",
            "CLI --> TaskState",
            "target artifact authority",
        ):
            with self.subTest(stale_claim=stale_claim):
                self.assertNotIn(stale_claim, combined)

        for shim in ("domain/agent/repository.py", "domain/task/repository.py"):
            with self.subTest(shim=shim):
                self.assertIn(shim, pipeline)
                self.assertIn(shim, adr)

        self.assertIn("Evolution may not", adr)
        self.assertIn("No third exception is permitted", adr)

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
