from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading

from ...application.ports.agent_execution import (
    ProcessExecution,
    ProcessExecutionRequest,
    ProcessObserver,
    ProcessStartError,
)


class OutputTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lines: list[str] = []

    def add_line(self, line: str) -> None:
        cleaned = line.strip()
        if not cleaned:
            return
        with self._lock:
            self._lines.append(cleaned)
            self._lines = self._lines[-10:]

    def summary(self) -> str | None:
        with self._lock:
            if not self._lines:
                return None
            recent = self._lines[-3:]
        return " | ".join(recent)[-240:]


class TrackedSubprocessAdapter:
    def run(
        self,
        request: ProcessExecutionRequest,
        observer: ProcessObserver,
    ) -> ProcessExecution:
        try:
            process = subprocess.Popen(
                list(request.command),
                cwd=Path(request.cwd),
                env=_build_process_env(dict(request.env)),
                stdin=subprocess.PIPE if request.stdin_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            raise ProcessStartError(str(error)) from error

        tracker = OutputTracker()
        output_thread = threading.Thread(
            target=_stream_output,
            kwargs={"process": process, "tracker": tracker},
            daemon=True,
        )
        output_thread.start()
        if request.stdin_text is not None and process.stdin is not None:
            process.stdin.write(request.stdin_text)
            process.stdin.close()

        observer.started(process.pid)
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            kwargs={
                "stop_event": stop_event,
                "observer": observer,
                "heartbeat_seconds": request.heartbeat_seconds,
                "tracker": tracker,
            },
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            _stop_threads(
                stop_event,
                output_thread,
                heartbeat_thread,
                heartbeat_seconds=request.heartbeat_seconds,
            )
            raise
        _stop_threads(
            stop_event,
            output_thread,
            heartbeat_thread,
            heartbeat_seconds=request.heartbeat_seconds,
        )
        return ProcessExecution(exit_code=exit_code, output_summary=tracker.summary())


def _stream_output(*, process: subprocess.Popen[str], tracker: OutputTracker) -> None:
    if process.stdout is None:
        return
    try:
        for line in process.stdout:
            tracker.add_line(line)
            _write_stdout_line(line)
    finally:
        process.stdout.close()


def _heartbeat_loop(
    *,
    stop_event: threading.Event,
    observer: ProcessObserver,
    heartbeat_seconds: int,
    tracker: OutputTracker,
) -> None:
    while not stop_event.wait(max(1, heartbeat_seconds)):
        if not observer.heartbeat(tracker.summary()):
            return


def _stop_threads(
    stop_event: threading.Event,
    output_thread: threading.Thread,
    heartbeat_thread: threading.Thread,
    *,
    heartbeat_seconds: int,
) -> None:
    stop_event.set()
    output_thread.join(timeout=heartbeat_seconds + 1)
    heartbeat_thread.join(timeout=heartbeat_seconds + 1)


def _build_process_env(overrides: dict[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if overrides:
        env.update(overrides)
    return env


def _write_stdout_line(line: str) -> None:
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(line.encode(encoding, errors="replace"))
            sys.stdout.flush()
            return
        sys.stdout.write(
            line.encode(encoding, errors="replace").decode(encoding, errors="replace")
        )
        sys.stdout.flush()


__all__ = ["OutputTracker", "TrackedSubprocessAdapter"]
