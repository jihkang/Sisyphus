from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time


MAX_VERIFICATION_COMMAND_CHARS = 32_768


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

    def run(self, command: str, *, cwd: Path) -> ShellCommandReceipt:
        normalized = parse_verification_command(command)
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                normalized,
                cwd=cwd,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            return ShellCommandReceipt(
                command=normalized,
                exit_code=127,
                duration_ms=_duration_ms(started),
                output_tail="",
                truncated_bytes=0,
                timed_out=False,
                error=str(exc),
            )

        if process.stdout is None:
            process.kill()
            raise RuntimeError("verification process stdout pipe was not created")
        os.set_blocking(process.stdout.fileno(), False)

        output = _TailBuffer(self.max_output_bytes)
        timed_out = False
        killed_at: float | None = None
        pipe_open = True
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = started + self.timeout_seconds
        try:
            while pipe_open or process.poll() is None:
                now = time.monotonic()
                if not timed_out and now >= deadline:
                    timed_out = True
                    killed_at = now
                    _kill_process_group(process)
                wait_for = 0.1
                if not timed_out:
                    wait_for = min(wait_for, max(deadline - now, 0.0))
                if pipe_open:
                    events = selector.select(wait_for)
                else:
                    time.sleep(wait_for)
                    events = ()
                for key, _mask in events:
                    try:
                        chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                    except BlockingIOError:
                        continue
                    if chunk:
                        output.append(chunk)
                    else:
                        selector.unregister(key.fileobj)
                        pipe_open = False
                if timed_out and killed_at is not None and time.monotonic() - killed_at >= 1.0:
                    pipe_open = False
        finally:
            selector.close()
            process.stdout.close()

        if process.poll() is None:
            _kill_process_group(process)
        try:
            return_code = process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait()

        error = None
        if timed_out:
            return_code = 124
            error = f"verification command timed out after {self.timeout_seconds:g} seconds"
        return ShellCommandReceipt(
            command=normalized,
            exit_code=return_code,
            duration_ms=_duration_ms(started),
            output_tail=output.render(),
            truncated_bytes=output.truncated_bytes,
            timed_out=timed_out,
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


class _TailBuffer:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._value = bytearray()
        self._total = 0

    @property
    def truncated_bytes(self) -> int:
        return max(self._total - len(self._value), 0)

    def append(self, chunk: bytes) -> None:
        self._total += len(chunk)
        self._value.extend(chunk)
        if len(self._value) > self._limit:
            del self._value[: len(self._value) - self._limit]

    def render(self) -> str:
        return bytes(self._value).decode("utf-8", errors="replace")


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _duration_ms(started: float) -> int:
    return max(int((time.monotonic() - started) * 1000), 0)


__all__ = [
    "BoundedShellCommandRunner",
    "MAX_VERIFICATION_COMMAND_CHARS",
    "ShellCommandReceipt",
    "parse_verification_command",
]
