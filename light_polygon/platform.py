from __future__ import annotations

import platform
from pathlib import Path
from typing import Callable


def get_system() -> str:
    """Return the current system identifier."""
    return platform.system()


def is_windows() -> bool:
    return get_system() == "Windows"


def is_macos() -> bool:
    return get_system() == "Darwin"


def is_linux() -> bool:
    return get_system() == "Linux"


def get_compiler_executable(lang: str = "cpp") -> str:
    """Get the compiler executable name for the current platform."""
    if lang in ("cpp", "c++"):
        return "g++"
    elif lang == "c":
        return "gcc"
    return "g++"


def normalize_executable_path(output_path: Path) -> Path:
    """Handle Windows .exe auto-appended by g++."""
    if output_path.exists():
        return output_path
    exe_path = Path(str(output_path) + ".exe")
    if exe_path.exists():
        return exe_path
    return output_path


def make_resource_limit_setter(
    time_limit_ms: int, memory_limit_mb: int
) -> Callable | None:
    """Return a preexec_fn for Unix resource limits, or None on Windows."""
    if is_windows():
        return None

    def _set_limits() -> None:
        try:
            import resource  # type: ignore[import-not-found]

            cpu_seconds = time_limit_ms / 1000.0 + 1
            resource.setrlimit(  # type: ignore
                resource.RLIMIT_CPU,
                (int(cpu_seconds) + 1, int(cpu_seconds) + 2),  # type: ignore
            )
            mem_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes * 2, mem_bytes * 2))  # type: ignore
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))  # type: ignore
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024)
            )  # type: ignore
        except (ImportError, ValueError, resource.error):  # type: ignore
            pass

    return _set_limits


def get_cpu_time_ms() -> int:
    """Get CPU time of child processes on Unix. Returns 0 on Windows."""
    if is_windows():
        return 0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return int((usage.ru_utime + usage.ru_stime) * 1000)
    except (ImportError, ValueError):
        return 0


def get_memory_kb() -> int:
    """Get max memory usage of child processes on Unix. Returns 0 on Windows."""
    if is_windows():
        return 0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        kb = usage.ru_maxrss
        if is_macos():
            kb //= 1024
        return kb
    except (ImportError, ValueError):
        return 0


def normalize_exit_code(code: int, stderr: str = "") -> int:
    """Normalize platform-specific exit codes.

    Handles known Windows MSYS2 testlib crashes (0xC0000005) that still
    produce correct output before crashing on exit.
    """
    if is_windows() and code == -1073741819:  # 0xC0000005
        if not stderr.strip():
            return 0
    return code
