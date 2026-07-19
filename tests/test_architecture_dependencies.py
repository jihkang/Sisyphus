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


# This is migration debt, not an accepted target architecture. Removing entries is
# always allowed; adding an outward dependency from domain is not.
LEGACY_DOMAIN_OUTWARD_DEPENDENCIES = frozenset(
    {
        (
            "src/sisyphus/domain/agent/repository.py",
            "sisyphus.infra.persistence.agent_repository",
        ),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.config"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.conformance"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.design"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.gates"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.lifecycle_guard"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.lifecycle_state"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.metrics"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.state"),
        ("src/sisyphus/domain/planning/service.py", "sisyphus.strategy"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.config"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.design"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.gates"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.infra.persistence.json_store"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.state"),
        ("src/sisyphus/domain/planning/spec_validation.py", "sisyphus.strategy"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.closeout"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.config"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.gitops"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.lifecycle_guard"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.lifecycle_state"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.metrics"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.promotion_state"),
        ("src/sisyphus/domain/promotion/service.py", "sisyphus.state"),
        ("src/sisyphus/domain/task/factory.py", "sisyphus.config"),
        ("src/sisyphus/domain/task/factory.py", "sisyphus.conformance"),
        ("src/sisyphus/domain/task/factory.py", "sisyphus.design"),
        ("src/sisyphus/domain/task/factory.py", "sisyphus.gitops"),
        ("src/sisyphus/domain/task/factory.py", "sisyphus.promotion_state"),
        (
            "src/sisyphus/domain/task/repository.py",
            "sisyphus.infra.persistence.task_repository",
        ),
        ("src/sisyphus/domain/workflow/candidates.py", "sisyphus.infra.persistence"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.audit"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.bus"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.closeout"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.config"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.conformance"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.events"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.metrics"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.obligation_runtime"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.planning"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.provider_wrapper"),
        ("src/sisyphus/domain/workflow/service.py", "sisyphus.state"),
    }
)

LEGACY_IMPORT_CYCLES = frozenset(
    {
        frozenset(
            {
                "sisyphus.daemon",
                "sisyphus.domain.workflow",
                "sisyphus.domain.workflow.service",
                "sisyphus.provider_wrapper",
                "sisyphus.workflow",
            }
        ),
        frozenset({"sisyphus.interfaces.mcp", "sisyphus.interfaces.mcp.service"}),
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

    def test_domain_outward_dependency_debt_cannot_grow(self) -> None:
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

        unexpected = actual - LEGACY_DOMAIN_OUTWARD_DEPENDENCIES

        self.assertFalse(
            unexpected,
            "domain gained outward dependencies:\n" + _format_pairs(unexpected),
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

    def test_import_cycles_cannot_grow(self) -> None:
        actual = frozenset(_strongly_connected_components(self.dependencies))
        unexpected = actual - LEGACY_IMPORT_CYCLES

        self.assertFalse(
            unexpected,
            "new import cycles detected:\n"
            + "\n".join(" -> ".join(sorted(cycle)) for cycle in sorted(unexpected, key=sorted)),
        )

    def test_removed_planning_lifecycle_cycle_stays_removed(self) -> None:
        cycle_members = {
            "sisyphus.domain.planning.service",
            "sisyphus.lifecycle_guard",
            "sisyphus.lifecycle_rules",
            "sisyphus.planning",
        }

        self.assertFalse(
            any(cycle_members <= cycle for cycle in _strongly_connected_components(self.dependencies)),
            "planning and lifecycle modules formed their previous import cycle",
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
