from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "sisyphus"

DOMAIN_IMPORT_COMPATIBILITY_SHIMS = frozenset(
    {
        (
            "src/sisyphus/domain/agent/repository.py",
            "sisyphus.infra.persistence.agent_repository",
        ),
        (
            "src/sisyphus/domain/task/repository.py",
            "sisyphus.infra.persistence.task_repository",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class ModuleSource:
    name: str
    path: Path
    package: str


class ArchitectureDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = _module_sources()
        cls.dependencies = {
            module.name: _internal_dependencies(module, cls.modules)
            for module in cls.modules.values()
        }

    def test_domain_has_no_outward_dependencies(self) -> None:
        actual: set[tuple[str, str]] = set()
        for module in self.modules.values():
            if not module.name.startswith("sisyphus.domain"):
                continue
            for dependency in _declared_imports(module):
                if not dependency.startswith("sisyphus."):
                    continue
                if dependency.startswith(("sisyphus.domain", "sisyphus.shared")):
                    continue
                relative_path = module.path.relative_to(PROJECT_ROOT).as_posix()
                actual.add((relative_path, dependency))

        self.assertEqual(
            actual,
            DOMAIN_IMPORT_COMPATIBILITY_SHIMS,
            "domain outward dependencies must be exactly the two documented import-compatibility "
            "shims:\n" + _format_pairs(actual),
        )

    def test_domain_compatibility_allowlist_contains_import_only_shims(self) -> None:
        for relative_path, _dependency in DOMAIN_IMPORT_COMPATIBILITY_SHIMS:
            path = PROJECT_ROOT / relative_path
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    continue
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    self.assertIsInstance(node.value.value, str, f"{relative_path} has executable code")
                    continue
                if isinstance(node, ast.Assign):
                    self.assertEqual(
                        [target.id for target in node.targets if isinstance(target, ast.Name)],
                        ["__all__"],
                        f"{relative_path} may assign only __all__",
                    )
                    self.assertTrue(
                        isinstance(node.value, (ast.List, ast.Tuple))
                        and all(
                            isinstance(item, ast.Constant) and isinstance(item.value, str)
                            for item in node.value.elts
                        ),
                        f"{relative_path} __all__ must be a literal string list",
                    )
                    continue
                self.fail(
                    f"{relative_path} contains {type(node).__name__}; compatibility shims must remain import-only"
                )

    def test_application_only_depends_on_inward_packages(self) -> None:
        forbidden: set[tuple[str, str]] = set()
        for module in self.modules.values():
            if not module.name.startswith("sisyphus.application"):
                continue
            for dependency in _declared_imports(module):
                if not dependency.startswith("sisyphus."):
                    continue
                if dependency.startswith(
                    ("sisyphus.application", "sisyphus.domain", "sisyphus.shared")
                ):
                    continue
                forbidden.add((module.name, dependency))

        self.assertFalse(forbidden, "application has outward dependencies:\n" + _format_pairs(forbidden))

    def test_interfaces_do_not_import_infrastructure_directly(self) -> None:
        forbidden = _dependencies_from_prefix(
            self.modules.values(),
            source_prefix="sisyphus.interfaces",
            dependency_prefixes=("sisyphus.infra",),
        )

        self.assertFalse(forbidden, "interfaces bypass application ports:\n" + _format_pairs(forbidden))

    def test_compat_modules_only_delegate_to_interfaces(self) -> None:
        forbidden: set[tuple[str, str]] = set()
        for module in self.modules.values():
            if not module.name.startswith("sisyphus.compat"):
                continue
            for dependency in _declared_imports(module):
                if dependency.startswith("sisyphus.") and not dependency.startswith("sisyphus.interfaces"):
                    forbidden.add((module.name, dependency))

        self.assertFalse(forbidden, "compat modules gained business dependencies:\n" + _format_pairs(forbidden))

    def test_internal_import_graph_is_acyclic(self) -> None:
        actual = frozenset(_strongly_connected_components(self.dependencies))

        self.assertFalse(
            actual,
            "import cycles detected:\n"
            + "\n".join(" -> ".join(sorted(cycle)) for cycle in sorted(actual, key=sorted)),
        )

    def test_removed_planning_lifecycle_cycle_stays_removed(self) -> None:
        cycle_members = {
            "sisyphus.infra.orchestration.planning",
            "sisyphus.lifecycle_guard",
            "sisyphus.lifecycle_rules",
            "sisyphus.planning",
        }

        self.assertFalse(
            any(cycle_members <= cycle for cycle in _strongly_connected_components(self.dependencies)),
            "planning and lifecycle modules formed their previous import cycle",
        )

    def test_provider_wrapper_does_not_depend_on_cli(self) -> None:
        module = self.modules["sisyphus.provider_wrapper"]
        forbidden = {
            dependency
            for dependency in _declared_imports(module)
            if dependency in {"sisyphus.cli", "sisyphus.interfaces.cli"}
            or dependency.startswith("sisyphus.interfaces.cli.")
        }

        self.assertFalse(
            forbidden,
            "provider wrapper regained a CLI dependency: " + ", ".join(sorted(forbidden)),
        )

    def test_provider_wrapper_does_not_reabsorb_boundary_mechanics(self) -> None:
        module = self.modules["sisyphus.provider_wrapper"]
        tree = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
        forbidden_modules = {"argparse", "json", "shutil", "subprocess", "tempfile"}
        actual: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                actual.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                actual.add(node.module.split(".", 1)[0])

        self.assertFalse(
            actual.intersection(forbidden_modules),
            "provider wrapper reabsorbed parser/process/receipt mechanics: "
            + ", ".join(sorted(actual.intersection(forbidden_modules))),
        )

    def test_conversation_provider_does_not_dispatch_through_daemon(self) -> None:
        module = self.modules["sisyphus.infra.providers.conversation"]
        dependencies = _declared_imports(module)

        self.assertNotIn(
            "sisyphus.daemon",
            dependencies,
            "conversation provider regained a daemon facade dependency",
        )
        tree = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
        dynamic_imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "importlib"
            for alias in node.names
        }
        self.assertFalse(
            dynamic_imports.intersection({"import_module"}),
            "conversation provider regained dynamic daemon dispatch",
        )

    def test_daemon_facade_does_not_reabsorb_concrete_effects(self) -> None:
        module = self.modules["sisyphus.daemon"]
        forbidden = {
            dependency
            for dependency in _declared_imports(module)
            if dependency
            in {
                "sisyphus.creation",
                "sisyphus.gitops",
                "sisyphus.infra.persistence",
                "sisyphus.promotion",
                "sisyphus.state",
            }
        }

        self.assertFalse(
            forbidden,
            "daemon facade regained concrete orchestration effects: "
            + ", ".join(sorted(forbidden)),
        )

    def test_infrastructure_does_not_import_config_or_event_facades(self) -> None:
        forbidden: set[tuple[str, str]] = set()
        facade_modules = {"sisyphus.bus", "sisyphus.bus_jsonl", "sisyphus.config"}
        for module in self.modules.values():
            if not module.name.startswith("sisyphus.infra"):
                continue
            for dependency in _declared_imports(module):
                if dependency in facade_modules:
                    forbidden.add((module.name, dependency))

        self.assertFalse(
            forbidden,
            "infrastructure imports public config/event facades:\n" + _format_pairs(forbidden),
        )

    def test_verification_and_lifecycle_adapters_do_not_import_public_facades(self) -> None:
        source_modules = {
            "sisyphus.infra.persistence.lifecycle_mapper",
            "sisyphus.infra.verification.adapters",
        }
        facade_modules = {
            "sisyphus.conformance",
            "sisyphus.evidence_graph",
            "sisyphus.gates",
            "sisyphus.promotion_state",
            "sisyphus.state",
        }
        forbidden: set[tuple[str, str]] = set()
        for name in source_modules:
            for dependency in _declared_imports(self.modules[name]):
                if dependency in facade_modules:
                    forbidden.add((name, dependency))

        self.assertFalse(
            forbidden,
            "verification/lifecycle adapters import public facades:\n" + _format_pairs(forbidden),
        )

    def test_spec_validation_adapters_do_not_import_public_facades(self) -> None:
        source_modules = {
            "sisyphus.infra.orchestration.planning_adapters",
            "sisyphus.infra.validation.spec_validation",
        }
        facade_modules = {
            "sisyphus.conformance",
            "sisyphus.design",
            "sisyphus.gates",
            "sisyphus.state",
            "sisyphus.strategy",
        }
        forbidden = {
            (name, dependency)
            for name in source_modules
            for dependency in _declared_imports(self.modules[name])
            if dependency in facade_modules
        }

        self.assertFalse(
            forbidden,
            "spec-validation adapters import public facades:\n" + _format_pairs(forbidden),
        )

    def test_provider_launch_and_receipt_adapters_do_not_import_public_facades(self) -> None:
        source_modules = {
            "sisyphus.infra.providers.launch",
            "sisyphus.infra.providers.local_config",
            "sisyphus.infra.providers.receipt_schema",
            "sisyphus.infra.providers.receipts",
        }
        forbidden_prefixes = (
            "sisyphus.codex_prompt",
            "sisyphus.providers",
            "sisyphus.state",
        )
        forbidden = {
            (name, dependency)
            for name in source_modules
            for dependency in _declared_imports(self.modules[name])
            if dependency.startswith(forbidden_prefixes)
        }

        self.assertFalse(
            forbidden,
            "provider launch/receipt adapters import public facades:\n"
            + _format_pairs(forbidden),
        )

    def test_workflow_adapter_has_no_root_facade_dependencies(self) -> None:
        module = self.modules["sisyphus.infra.orchestration.workflow_adapters"]
        dependencies = _declared_imports(module)
        outward = {
            dependency
            for dependency in dependencies
            if dependency.startswith("sisyphus.")
            and not dependency.startswith(
                (
                    "sisyphus.application",
                    "sisyphus.domain",
                    "sisyphus.infra",
                    "sisyphus.shared",
                )
            )
        }

        self.assertFalse(
            outward,
            "workflow adapter imports root facades:\n" + "\n".join(sorted(outward)),
        )

    def test_domain_models_do_not_own_boundary_mapping_methods(self) -> None:
        violations: set[tuple[str, str]] = set()
        for module in self.modules.values():
            if not module.name.startswith("sisyphus.domain"):
                continue
            tree = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name in {
                        "from_dict",
                        "to_dict",
                    }:
                        violations.add((f"{module.name}.{node.name}", member.name))

        self.assertFalse(
            violations,
            "domain models own persistence/transport mapping:\n" + _format_pairs(violations),
        )


def _module_sources() -> dict[str, ModuleSource]:
    result: dict[str, ModuleSource] = {}
    for path in PACKAGE_ROOT.rglob("*.py"):
        parts = list(path.relative_to(SRC_ROOT).with_suffix("").parts)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts.pop()
        name = ".".join(parts)
        package = name if is_package else name.rpartition(".")[0]
        result[name] = ModuleSource(name=name, path=path, package=package)
    return result


def _declared_imports(module: ModuleSource) -> set[str]:
    tree = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            dependency = importlib.util.resolve_name(
                "." * node.level + (node.module or ""),
                module.package,
            )
        else:
            dependency = node.module or ""
        if dependency:
            imports.add(dependency)
        if node.module is None:
            imports.update(f"{dependency}.{alias.name}" for alias in node.names)
    return imports


def _internal_dependencies(
    module: ModuleSource,
    modules: dict[str, ModuleSource],
) -> set[str]:
    return {dependency for dependency in _declared_imports(module) if dependency in modules}


def _dependencies_from_prefix(
    modules: Iterable[ModuleSource],
    *,
    source_prefix: str,
    dependency_prefixes: tuple[str, ...],
) -> set[tuple[str, str]]:
    forbidden: set[tuple[str, str]] = set()
    for module in modules:
        if not module.name.startswith(source_prefix):
            continue
        for dependency in _declared_imports(module):
            if dependency.startswith(dependency_prefixes):
                forbidden.add((module.name, dependency))
    return forbidden


def _strongly_connected_components(
    graph: dict[str, set[str]],
) -> set[frozenset[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: set[frozenset[str]] = set()

    def visit(node: str) -> None:
        nonlocal index
        index += 1
        indices[node] = index
        lowlinks[node] = index
        stack.append(node)
        on_stack.add(node)

        for dependency in graph[node]:
            if dependency not in indices:
                visit(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])

        if lowlinks[node] != indices[node]:
            return
        component: set[str] = set()
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        if len(component) > 1:
            components.add(frozenset(component))

    for node in graph:
        if node not in indices:
            visit(node)
    return components


def _format_pairs(items: set[tuple[str, str]]) -> str:
    return "\n".join(f"{source} -> {dependency}" for source, dependency in sorted(items))


if __name__ == "__main__":
    unittest.main()
