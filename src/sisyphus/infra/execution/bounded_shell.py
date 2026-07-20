from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from typing import BinaryIO


MAX_SHELL_COMMAND_CHARS = 32_768


@dataclass(frozen=True, slots=True)
class BoundedShellProcessReceipt:
    command: str
    exit_code: int
    duration_ms: int
    stdout_tail: str
    stderr_tail: str
    stdout_truncated_bytes: int
    stderr_truncated_bytes: int
    timed_out: bool
    error: str | None = None


class BoundedShellProcessRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = 300.0,
        max_output_bytes: int = 64_000,
    ) -> None:
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.max_output_bytes = max(int(max_output_bytes), 256)

    def run(
        self,
        command: str,
        *,
        cwd: Path,
        merge_stderr: bool = False,
    ) -> BoundedShellProcessReceipt:
        normalized = normalize_shell_command(command)
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                normalized,
                cwd=cwd,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            return BoundedShellProcessReceipt(
                command=normalized,
                exit_code=127,
                duration_ms=_duration_ms(started),
                stdout_tail="",
                stderr_tail="",
                stdout_truncated_bytes=0,
                stderr_truncated_bytes=0,
                timed_out=False,
                error=str(exc),
            )

        if process.stdout is None:
            _kill_process_group(process)
            raise RuntimeError("bounded process stdout pipe was not created")

        stdout = _TailBuffer(self.max_output_bytes)
        stderr = _TailBuffer(self.max_output_bytes)
        stream_buffers: list[tuple[BinaryIO, _TailBuffer]] = [
            (process.stdout, stdout),
        ]
        if not merge_stderr:
            if process.stderr is None:
                _kill_process_group(process)
                process.stdout.close()
                raise RuntimeError("bounded process stderr pipe was not created")
            stream_buffers.append((process.stderr, stderr))

        selector = selectors.DefaultSelector()
        open_streams: dict[int, tuple[BinaryIO, _TailBuffer]] = {}
        for stream, buffer in stream_buffers:
            descriptor = stream.fileno()
            os.set_blocking(descriptor, False)
            selector.register(stream, selectors.EVENT_READ)
            open_streams[descriptor] = (stream, buffer)

        timed_out = False
        killed_at: float | None = None
        deadline = started + self.timeout_seconds
        try:
            while open_streams or process.poll() is None:
                now = time.monotonic()
                if not timed_out and now >= deadline:
                    timed_out = True
                    killed_at = now
                    _kill_process_group(process)

                wait_for = 0.1
                if not timed_out:
                    wait_for = min(wait_for, max(deadline - now, 0.0))
                events = selector.select(wait_for) if open_streams else ()
                for key, _mask in events:
                    stream = key.fileobj
                    descriptor = stream.fileno()
                    try:
                        chunk = os.read(descriptor, 64 * 1024)
                    except BlockingIOError:
                        continue
                    if chunk:
                        open_streams[descriptor][1].append(chunk)
                        continue
                    selector.unregister(stream)
                    open_streams.pop(descriptor, None)

                if (
                    timed_out
                    and killed_at is not None
                    and time.monotonic() - killed_at >= 1.0
                ):
                    break
        finally:
            selector.close()
            for stream, _buffer in stream_buffers:
                stream.close()

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
            error = f"command timed out after {self.timeout_seconds:g} seconds"
        return BoundedShellProcessReceipt(
            command=normalized,
            exit_code=return_code,
            duration_ms=_duration_ms(started),
            stdout_tail=stdout.render(),
            stderr_tail=stderr.render(),
            stdout_truncated_bytes=stdout.truncated_bytes,
            stderr_truncated_bytes=stderr.truncated_bytes,
            timed_out=timed_out,
            error=error,
        )


def normalize_shell_command(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("shell command must be a string")
    command = value.strip()
    if not command:
        raise ValueError("shell command must not be empty")
    if "\x00" in command or "\n" in command or "\r" in command:
        raise ValueError("shell command must be a single NUL-free line")
    if len(command) > MAX_SHELL_COMMAND_CHARS:
        raise ValueError(
            f"shell command exceeds {MAX_SHELL_COMMAND_CHARS} characters"
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
    "BoundedShellProcessReceipt",
    "BoundedShellProcessRunner",
    "MAX_SHELL_COMMAND_CHARS",
    "normalize_shell_command",
]
