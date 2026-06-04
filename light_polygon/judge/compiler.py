from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from light_polygon.config import get_config
from light_polygon.platform import (
    get_compiler_executable,
    is_windows,
    normalize_executable_path,
)


@dataclass
class CompileResult:
    success: bool
    executable_path: Path | None = None
    errors: str = ""


DEFAULT_FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wextra"]
if is_windows():
    # Static link libgcc/libstdc++ to avoid Windows MSYS2 runtime crashes
    # (known issue with testlib programs exiting with 0xC0000005)
    DEFAULT_FLAGS.extend(["-static-libgcc", "-static-libstdc++"])


def _get_cache_dir() -> Path:
    return get_config().data_dir / ".cache" / "compile"


def _compute_cache_key(
    source_path: Path,
    language: str,
    flags: list[str] | None,
    include_dirs: list[str] | None,
    defines: list[str] | None,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(source_path.read_bytes())
    hasher.update(language.encode())
    if flags:
        hasher.update(",".join(flags).encode())
    if include_dirs:
        hasher.update(",".join(include_dirs).encode())
    if defines:
        hasher.update(",".join(defines).encode())
    return hasher.hexdigest()


def compile_source(
    source_path: Path,
    language: str = "cpp",
    output_path: Path | None = None,
    flags: list[str] | None = None,
    include_dirs: list[str] | None = None,
    defines: list[str] | None = None,
) -> CompileResult:
    """Compile a source file to an executable.

    Args:
        source_path: Path to the source file.
        language: Language identifier (cpp, c, etc.).
        output_path: Optional explicit output path. If None, uses a temp file.
        flags: Additional compiler flags. If None, uses DEFAULT_FLAGS for C++.
        include_dirs: List of include directories (-I).
        defines: List of macro definitions (-D).

    Returns:
        CompileResult with the path to the compiled executable.
    """
    if not source_path.exists():
        return CompileResult(
            success=False, errors=f"Source file not found: {source_path}"
        )

    # If it's an interpreted language or already compiled
    if language not in ("cpp", "c++", "c"):
        return CompileResult(success=True, executable_path=source_path)

    use_cache = output_path is None

    if use_cache:
        cache_key = _compute_cache_key(
            source_path,
            language,
            flags,
            include_dirs,
            defines,
        )
        cache_dir = _get_cache_dir() / cache_key
        output_path = cache_dir / source_path.stem
        cached = normalize_executable_path(output_path)
        if cached.exists():
            return CompileResult(success=True, executable_path=cached)
        cache_dir.mkdir(parents=True, exist_ok=True)
    elif output_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="lp_compile_"))
        output_path = temp_dir / source_path.stem

    compiler = get_compiler_executable(language)

    cmd = [compiler]

    if flags is not None:
        cmd.extend(flags)
    elif language in ("cpp", "c++"):
        cmd.extend(DEFAULT_FLAGS)

    if include_dirs:
        for inc_dir in reversed(include_dirs):
            cmd.insert(1, f"-I{inc_dir}")

    if defines:
        for d in defines:
            cmd.insert(1, f"-D{d}")

    cmd.extend(["-o", str(output_path), str(source_path)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            exe_path = normalize_executable_path(output_path)
            return CompileResult(success=True, executable_path=exe_path)
        else:
            return CompileResult(
                success=False,
                errors=result.stderr or result.stdout or "Compilation failed",
            )
    except subprocess.TimeoutExpired:
        return CompileResult(success=False, errors="Compilation timed out")
    except FileNotFoundError:
        return CompileResult(
            success=False,
            errors=f"Compiler not found: {compiler}. Please install g++.",
        )
