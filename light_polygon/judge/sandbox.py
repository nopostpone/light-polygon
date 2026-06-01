from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from light_polygon.platform import (
    get_cpu_time_ms,
    get_memory_kb,
    make_resource_limit_setter,
    normalize_exit_code,
)

MAX_OUTPUT_BYTES = 64 * 1024 * 1024  # 64 MB limit on stdout/stderr


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    cpu_time_ms: int = 0
    wall_time_ms: int = 0
    memory_kb: int = 0
    verdict: str = ""
    error: str = ""


def run_sandboxed(
    cmd: list[str],
    *,
    time_limit_ms: int = 2000,
    memory_limit_mb: int = 256,
    stdin_data: str = "",
    stdin_path: Path | None = None,
    working_dir: Path | None = None,
) -> SandboxResult:
    """Run a command in a sandbox with resource limits.

    Args:
        cmd: Command and arguments.
        time_limit_ms: CPU time limit in milliseconds.
        memory_limit_mb: Memory limit in megabytes.
        stdin_data: String data to feed to stdin.
        stdin_path: Path to a file to redirect to stdin (mutually exclusive with stdin_data).
        working_dir: Working directory for the process.
    """
    start = time.monotonic()
    wall_limit = (time_limit_ms / 1000.0) + 3  # 3 extra seconds for wall-clock

    stdin_file = None
    try:
        preexec_fn = make_resource_limit_setter(time_limit_ms, memory_limit_mb)

        if stdin_path is not None:
            stdin_file = open(stdin_path, "rb")
            stdin_arg = stdin_file
        else:
            stdin_arg = subprocess.PIPE

        proc = psutil.Popen(
            cmd,
            stdin=stdin_arg,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(working_dir) if working_dir else None,
            preexec_fn=preexec_fn,
        )

        try:
            if stdin_path is not None:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=wall_limit)
            else:
                stdout_bytes, stderr_bytes = proc.communicate(
                    input=stdin_data.encode("utf-8", errors="replace"),
                    timeout=wall_limit,
                )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate(timeout=5)

        wall_time_ms = int((time.monotonic() - start) * 1000)
        exit_code = proc.returncode

        cpu_time_ms = get_cpu_time_ms()
        memory_kb = get_memory_kb()

        stderr_text = (
            (stderr_bytes or b"").decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
        )
        exit_code = normalize_exit_code(exit_code, stderr_text)

        stdout = (
            (stdout_bytes or b"").decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
        )
        stdout = stdout.replace("\r\n", "\n")
        stderr_text = stderr_text.replace("\r\n", "\n")

        verdict = "AC"
        error = ""

        if wall_time_ms > time_limit_ms:
            verdict = "TLE"
            error = f"Time limit exceeded: {wall_time_ms}ms > {time_limit_ms}ms"
        elif memory_kb > memory_limit_mb * 1024:
            verdict = "MLE"
            error = f"Memory limit exceeded: {memory_kb}KB > {memory_limit_mb * 1024}KB"
        elif exit_code != 0:
            verdict = "RTE"
            error = f"Runtime error: exit code {exit_code}"

        return SandboxResult(
            stdout=stdout,
            stderr=stderr_text,
            exit_code=exit_code,
            cpu_time_ms=cpu_time_ms,
            wall_time_ms=wall_time_ms,
            memory_kb=memory_kb,
            verdict=verdict,
            error=error,
        )

    except Exception as e:
        wall_time_ms = int((time.monotonic() - start) * 1000)
        return SandboxResult(
            verdict="RTE",
            error=f"Sandbox error: {e}",
            wall_time_ms=wall_time_ms,
        )
    finally:
        if stdin_file is not None:
            stdin_file.close()
