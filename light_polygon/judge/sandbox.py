from __future__ import annotations

import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

MAX_OUTPUT_BYTES = 64 * 1024 * 1024  # 64 MB limit on stdout/stderr


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    cpu_time_ms: int = 0
    wall_time_ms: int = 0
    memory_kb: int = 0
    verdict: str = ""  # AC, TLE, MLE, RTE
    error: str = ""


def _set_resource_limits(time_limit_ms: int, memory_limit_mb: int) -> None:
    """Set resource limits on Unix. Called in child process before exec."""
    try:
        import resource
        cpu_seconds = time_limit_ms / 1000.0 + 1  # 1s grace
        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds) + 1, int(cpu_seconds) + 2))
        mem_bytes = memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes * 2, mem_bytes * 2))
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    except (ImportError, ValueError, resource.error):
        pass


def run_sandboxed(
    cmd: list[str],
    *,
    time_limit_ms: int = 2000,
    memory_limit_mb: int = 256,
    stdin_data: str = "",
    working_dir: Path | None = None,
) -> SandboxResult:
    start = time.monotonic()
    wall_limit = (time_limit_ms / 1000.0) + 3  # 3 extra seconds for wall-clock

    try:
        is_unix = platform.system() != "Windows"

        proc = psutil.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(working_dir) if working_dir else None,
            preexec_fn=(lambda: _set_resource_limits(time_limit_ms, memory_limit_mb)) if is_unix else None,
        )

        try:
            stdout_bytes, stderr_bytes = proc.communicate(
                input=stdin_data.encode("utf-8", errors="replace"),
                timeout=wall_limit,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate(timeout=5)

        wall_time_ms = int((time.monotonic() - start) * 1000)
        exit_code = proc.returncode

        cpu_time_ms = 0
        memory_kb = 0
        try:
            if is_unix:
                import resource
                usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                cpu_time_ms = int((usage.ru_utime + usage.ru_stime) * 1000)
                memory_kb = usage.ru_maxrss  # KB on Linux, bytes on macOS
                if platform.system() == "Darwin":
                    memory_kb //= 1024
        except (ImportError, ValueError):
            pass

        if proc.returncode == -9 or proc.returncode == -15:
            # Killed by signal
            pass

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES] if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES] if stderr_bytes else ""
        # Normalize Windows CRLF -> LF for cross-platform consistency
        stdout = stdout.replace("\r\n", "\n")
        stderr = stderr.replace("\r\n", "\n")

        verdict = "AC"
        error = ""

        if wall_time_ms > time_limit_ms:
            verdict = "TLE"
            error = f"Time limit exceeded: {wall_time_ms}ms > {time_limit_ms}ms"
        elif memory_kb > memory_limit_mb * 1024:
            verdict = "MLE"
            error = f"Memory limit exceeded: {memory_kb}KB > {memory_limit_mb * 1024}KB"
        elif exit_code != 0 and exit_code != -9 and exit_code != -15:
            verdict = "RTE"
            error = f"Runtime error: exit code {exit_code}"

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
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
