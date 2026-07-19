from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import re
import shlex

from ...application.ports.workspace import SUPPORTED_WORKSPACE_ACTIONS
from ...domain.agent.workspace import WorkspaceCompletion, WorkspaceExecutionState
from .effects import WorkspaceGitEffects, WorkspaceTestEffects
from .errors import WorkspaceActionError, WorkspaceFileSafetyError, WorkspaceGitError
from .git import SubprocessWorkspaceGit
from .mutation_guard import TreeHashMutationGuard, WorkspaceTreeMutation
from .secure_files import SecureWorkspaceFiles
from .test_runner import SubprocessWorkspaceTests


PROTECTED_PATH_PARTS = {".git", ".planning"}
MAX_READ_FILE_BYTES = 1_000_000
SUPPORTED_ACTIONS = set(SUPPORTED_WORKSPACE_ACTIONS)


class WorkspaceExecutor:
    def __init__(
        self,
        workspace: Path,
        *,
        owned_paths: tuple[str, ...] = (),
        test_commands: tuple[str, ...] = (),
        command_timeout_seconds: float = 120.0,
        max_output_chars: int = 8000,
        git_effects: WorkspaceGitEffects | None = None,
        test_effects: WorkspaceTestEffects | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise WorkspaceActionError(f"local agent workspace does not exist: {workspace}")
        self.owned_paths = tuple(_normalize_relative_path(path) for path in owned_paths if path.strip())
        self.test_commands = tuple(command for command in test_commands if command.strip())
        self.command_timeout_seconds = max(float(command_timeout_seconds), 0.1)
        self.max_output_chars = max(int(max_output_chars), 256)
        self._files = SecureWorkspaceFiles(self.workspace)
        self._mutations = TreeHashMutationGuard(self._files)
        self._state = WorkspaceExecutionState()
        self._git = git_effects or SubprocessWorkspaceGit(
            self.workspace,
            timeout_seconds=self.command_timeout_seconds,
        )
        self._tests = test_effects or SubprocessWorkspaceTests(
            self.workspace,
            commands=self.test_commands,
            timeout_seconds=self.command_timeout_seconds,
        )

    @property
    def baseline_test_step(self) -> int | None:
        return self._state.baseline_test_step

    @property
    def last_mutation_step(self) -> int | None:
        return self._state.last_mutation_step

    @property
    def last_successful_test_step(self) -> int | None:
        return self._state.last_successful_test_step

    @property
    def blocked_action_count(self) -> int:
        return self._state.blocked_action_count

    @property
    def mutated_paths(self) -> set[str]:
        return self._state.mutated_paths

    def execute(self, action: Mapping[str, object], *, step: int) -> dict[str, object]:
        action_name = str(action.get("action") or "")
        if action_name not in SUPPORTED_ACTIONS:
            return self._blocked(f"unknown workspace action: {action_name or '<empty>'}")
        try:
            if action_name == "list_files":
                return self._list_files(action)
            if action_name == "read_file":
                return self._read_file(action)
            if action_name == "search":
                return self._search(action)
            if action_name == "write_file":
                result = self._write_file(action)
                if result["ok"] and result.get("mutated") is True:
                    self._state.record_mutation(step, (str(result["path"]),))
                return result
            if action_name == "apply_patch":
                result = self._apply_patch(action)
                if result["ok"] and result.get("mutated") is True:
                    self._state.record_mutation(
                        step,
                        (str(path) for path in result["changed_paths"]),
                    )
                return result
            if action_name == "git_diff":
                return self._git_diff()
            if action_name == "run_test":
                result = self._run_test(action)
                result["test_first_phase"] = self._state.record_test(
                    step,
                    passed=result["ok"] is True,
                )
                return result
        except (WorkspaceActionError, WorkspaceFileSafetyError) as exc:
            return self._blocked(str(exc))
        except WorkspaceGitError as exc:
            return self._blocked(self._bounded(str(exc)))
        except (OSError, UnicodeError) as exc:
            return {
                "ok": False,
                "blocked": False,
                "error": str(exc),
            }
        raise AssertionError(f"unhandled workspace action: {action_name}")

    def completion_facts(self) -> dict[str, object]:
        return _present_completion(self._state.evaluate_completion(self.changed_files()))

    def changed_files(self) -> list[str]:
        paths = {
            path
            for path in self._git.changed_files()
            if not _is_protected_relative_path(path)
        }
        return sorted(paths)

    def _list_files(self, action: Mapping[str, object]) -> dict[str, object]:
        requested = str(action.get("path") or ".")
        prefix = "" if requested in {"", "."} else _normalize_relative_path(requested).as_posix().rstrip("/") + "/"
        files = [path for path in self._repository_files() if not prefix or path.startswith(prefix)]
        output = "\n".join(files[:500])
        if len(files) > 500:
            output += f"\n... {len(files) - 500} more files"
        return {"ok": True, "blocked": False, "output": self._bounded(output), "file_count": len(files)}

    def _read_file(self, action: Mapping[str, object]) -> dict[str, object]:
        relative = _normalize_relative_path(_required_string(action, "path"))
        self._resolve_path(relative.as_posix(), write=False)
        start_line = _positive_int(action.get("start_line"), default=1)
        end_line = _positive_int(action.get("end_line"), default=start_line + 399)
        if end_line < start_line:
            raise WorkspaceActionError("end_line must be greater than or equal to start_line")
        try:
            lines = self._files.read_text(relative, max_bytes=MAX_READ_FILE_BYTES).splitlines()
        except FileNotFoundError as exc:
            raise WorkspaceActionError(f"file does not exist: {relative.as_posix()}") from exc
        selected = lines[start_line - 1 : min(end_line, len(lines))]
        rendered = "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(selected, start=start_line)
        )
        return {
            "ok": True,
            "blocked": False,
            "path": relative.as_posix(),
            "output": self._bounded(rendered),
            "line_count": len(lines),
        }

    def _search(self, action: Mapping[str, object]) -> dict[str, object]:
        query = _required_string(action, "query")
        requested = str(action.get("path") or ".")
        prefix = "" if requested in {"", "."} else _normalize_relative_path(requested).as_posix().rstrip("/") + "/"
        matches: list[str] = []
        for relative in self._repository_files():
            if prefix and not relative.startswith(prefix):
                continue
            try:
                lines = self._files.read_text(
                    PurePosixPath(relative),
                    max_bytes=MAX_READ_FILE_BYTES,
                ).splitlines()
            except (OSError, UnicodeError, WorkspaceFileSafetyError):
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    matches.append(f"{relative}:{line_number}:{line}")
                    if len(matches) >= 200:
                        break
            if len(matches) >= 200:
                break
        return {
            "ok": True,
            "blocked": False,
            "output": self._bounded("\n".join(matches)),
            "match_count": len(matches),
        }

    def _write_file(self, action: Mapping[str, object]) -> dict[str, object]:
        relative = _normalize_relative_path(_required_string(action, "path"))
        self._resolve_path(relative.as_posix(), write=True)
        content = action.get("content")
        if not isinstance(content, str):
            raise WorkspaceActionError("write_file requires string content")
        if len(content) > 250_000:
            raise WorkspaceActionError("write_file content exceeds 250000 characters")
        self._require_baseline_test()
        mutated = self._files.write_text_atomic(relative, content)
        if not mutated:
            return {
                "ok": True,
                "blocked": False,
                "mutated": False,
                "path": relative.as_posix(),
                "no_op": True,
                "guidance": "file already has this content; run a configured test instead of repeating the write",
            }
        return {
            "ok": True,
            "blocked": False,
            "mutated": True,
            "path": relative.as_posix(),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _apply_patch(self, action: Mapping[str, object]) -> dict[str, object]:
        patch = action.get("patch")
        if not isinstance(patch, str) or not patch.strip():
            raise WorkspaceActionError("apply_patch requires a non-empty patch")
        if len(patch) > 500_000:
            raise WorkspaceActionError("patch exceeds 500000 characters")
        if re.search(r"^(?:new file mode|new mode) 120000$", patch, re.MULTILINE):
            raise WorkspaceActionError("patches may not create symbolic links")
        paths = _paths_from_patch(patch)
        if not paths:
            raise WorkspaceActionError("patch does not declare any file paths")
        for relative in paths:
            self._resolve_path(relative, write=True)
        self._require_baseline_test()
        before = self._mutations.capture()
        execution = self._git.apply_patch(patch)
        mutation = self._mutations.inspect(
            before,
            declared_paths=frozenset(paths),
        )
        if not execution.ok:
            if mutation.changed_paths:
                raise WorkspaceActionError(
                    "git apply failed after mutating the workspace: "
                    + ", ".join(mutation.changed_paths)
                )
            return {
                "ok": False,
                "blocked": False,
                "error": self._bounded(execution.error or "git apply failed"),
            }
        self._require_safe_patch_mutation(mutation)
        return {
            "ok": True,
            "blocked": False,
            "mutated": True,
            "changed_paths": list(mutation.changed_paths),
            "tree_hash_before": mutation.before_hash,
            "tree_hash_after": mutation.after_hash,
        }

    @staticmethod
    def _require_safe_patch_mutation(mutation: WorkspaceTreeMutation) -> None:
        if mutation.protected_paths:
            raise WorkspaceActionError(
                "patch mutated protected workspace paths: "
                + ", ".join(mutation.protected_paths)
            )
        if mutation.unexpected_paths:
            raise WorkspaceActionError(
                "patch mutated paths it did not declare: "
                + ", ".join(mutation.unexpected_paths)
            )
        if mutation.non_regular_paths:
            raise WorkspaceActionError(
                "patch mutation includes a symbolic link or special file: "
                + ", ".join(mutation.non_regular_paths)
            )
        if not mutation.changed_paths:
            raise WorkspaceActionError("patch reported success without changing a regular file")

    def _git_diff(self) -> dict[str, object]:
        status = self._git.status()
        diff = self._git.diff_stat()
        return {
            "ok": True,
            "blocked": False,
            "output": self._bounded("status:\n" + status + "\ndiff:\n" + diff),
            "changed_files": self.changed_files(),
        }

    def _run_test(self, action: Mapping[str, object]) -> dict[str, object]:
        command_id = action.get("command_id")
        if not isinstance(command_id, int):
            raise WorkspaceActionError("run_test requires an integer command_id")
        execution = self._tests.run(command_id)
        return {
            "ok": execution.ok,
            "blocked": False,
            "command_id": execution.command_id,
            **({"exit_code": execution.exit_code} if execution.exit_code is not None else {}),
            "output": self._bounded(execution.output),
            "error": execution.error,
        }

    def _resolve_path(self, value: str, *, write: bool) -> Path:
        relative = _normalize_relative_path(value)
        if _is_protected_relative_path(relative.as_posix()):
            raise WorkspaceActionError(f"protected workspace path is not available to the local agent: {relative}")
        candidate = (self.workspace / Path(*relative.parts)).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise WorkspaceActionError(f"path escapes local agent workspace: {value}") from exc
        resolved_relative = candidate.relative_to(self.workspace).as_posix()
        if _is_protected_relative_path(resolved_relative):
            raise WorkspaceActionError(
                f"protected workspace path is not available to the local agent: {relative}"
            )
        self._files.reject_existing_symlinks(relative)
        if write and self.owned_paths and not any(
            relative == owned or owned in relative.parents
            for owned in self.owned_paths
        ):
            raise WorkspaceActionError(f"write path is outside the task owned scope: {relative}")
        return candidate

    def _require_baseline_test(self) -> None:
        if self.baseline_test_step is None:
            raise WorkspaceActionError(
                "run a configured baseline test before the first write or patch"
            )

    def _repository_files(self) -> list[str]:
        return sorted(
            {
                path
                for path in self._git.repository_files()
                if not _is_protected_relative_path(path)
            }
        )

    def _bounded(self, value: str) -> str:
        if len(value) <= self.max_output_chars:
            return value
        omitted = len(value) - self.max_output_chars
        return value[: self.max_output_chars] + f"\n... truncated {omitted} characters"

    def _blocked(self, error: str) -> dict[str, object]:
        self._state.record_blocked_action()
        return {"ok": False, "blocked": True, "error": error}


def _normalize_relative_path(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or normalized == ".":
        return PurePosixPath(".")
    if path.is_absolute() or ".." in path.parts:
        raise WorkspaceActionError(f"path must stay relative to the local agent workspace: {value}")
    return path


def _is_protected_relative_path(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return any(part in PROTECTED_PATH_PARTS for part in path.parts)


def _required_string(action: Mapping[str, object], key: str) -> str:
    value = action.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceActionError(f"{action.get('action')} requires a non-empty {key}")
    return value


def _positive_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or value < 1:
        raise WorkspaceActionError("line numbers must be positive integers")
    return value


def _paths_from_patch(patch: str) -> set[str]:
    paths: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            try:
                parts = shlex.split(line)
            except ValueError as exc:
                raise WorkspaceActionError("patch contains an invalid diff header") from exc
            if len(parts) != 4:
                raise WorkspaceActionError("patch diff header must declare exactly two paths")
            for raw in parts[2:]:
                paths.add(_strip_patch_prefix(raw))
        elif re.match(r"^(?:---|\+\+\+) ", line):
            raw = line.split(maxsplit=1)[1].split("\t", 1)[0]
            if raw != "/dev/null":
                paths.add(_strip_patch_prefix(raw))
    return {path for path in paths if path and path != "/dev/null"}


def _strip_patch_prefix(value: str) -> str:
    if value.startswith(("a/", "b/")):
        return value[2:]
    return value


def _present_completion(completion: WorkspaceCompletion) -> dict[str, object]:
    return {
        "completion_ready": completion.completion_ready,
        "reason": completion.reason,
        "changed_files": list(completion.changed_files),
        "last_mutation_step": completion.last_mutation_step,
        "last_successful_test_step": completion.last_successful_test_step,
        "baseline_test_step": completion.baseline_test_step,
    }


__all__ = [
    "PROTECTED_PATH_PARTS",
    "MAX_READ_FILE_BYTES",
    "SUPPORTED_ACTIONS",
    "WorkspaceActionError",
    "WorkspaceExecutor",
]
