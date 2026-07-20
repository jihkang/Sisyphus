from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..execution.bounded_shell import (
    BoundedShellProcessRunner,
    MAX_SHELL_COMMAND_CHARS,
)


MAX_VERIFICATION_COMMAND_CHARS = MAX_SHELL_COMMAND_CHARS


@dataclass(frozen=True, slots=True)
class ShellCommandReceipt:
    command: str
    exit_code: int
    duration_ms: int
    output_tail: str
    truncated_bytes: int
    timed_out: bool
    error: str | None = None


class BoundedShellCommandRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = 300.0,
        max_output_bytes: int = 64_000,
    ) -> None:
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.max_output_bytes = max(int(max_output_bytes), 256)
        self._runner = BoundedShellProcessRunner(
            timeout_seconds=self.timeout_seconds,
            max_output_bytes=self.max_output_bytes,
        )

    def run(self, command: str, *, cwd: Path) -> ShellCommandReceipt:
        normalized = parse_verification_command(command)
        bounded = self._runner.run(normalized, cwd=cwd, merge_stderr=True)
        error = bounded.error
        if bounded.timed_out:
            error = (
                "verification command timed out after "
                f"{self.timeout_seconds:g} seconds"
            )
        return ShellCommandReceipt(
            command=normalized,
            exit_code=bounded.exit_code,
            duration_ms=bounded.duration_ms,
            output_tail=bounded.stdout_tail,
            truncated_bytes=bounded.stdout_truncated_bytes,
            timed_out=bounded.timed_out,
            error=error,
        )


def parse_verification_command(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("verification command must be a string")
    command = value.strip()
    if not command:
        raise ValueError("verification command must not be empty")
    if "\x00" in command or "\n" in command or "\r" in command:
        raise ValueError("verification command must be a single NUL-free line")
    if len(command) > MAX_VERIFICATION_COMMAND_CHARS:
        raise ValueError(
            f"verification command exceeds {MAX_VERIFICATION_COMMAND_CHARS} characters"
        )
    return command


__all__ = [
    "BoundedShellCommandRunner",
    "MAX_VERIFICATION_COMMAND_CHARS",
    "ShellCommandReceipt",
    "parse_verification_command",
]
