from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

COMPILE_COMMANDS: dict[str, list[str]] = {
    "cpp": ["g++", "-std=c++17", "-O2", "-Wall", "-o", "{out}", "{src}"],
    "c": ["gcc", "-O2", "-Wall", "-o", "{out}", "{src}"],
}


@dataclass
class CompileResult:
    success: bool
    executable_path: Path | None = None
    errors: str = ""


def compile_source(source_path: Path, language: str,
                   cache_dir: Path | None = None,
                   include_dirs: list[str] | None = None,
                   defines: list[str] | None = None) -> CompileResult:
    if language not in COMPILE_COMMANDS:
        return CompileResult(success=True, executable_path=source_path)

    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_bin = cache_dir / f"{source_path.stem}_{source_hash}"
        # g++ on Windows auto-appends .exe; check both variants
        if cached_bin.exists():
            return CompileResult(success=True, executable_path=cached_bin)
        alt_exe = Path(str(cached_bin) + ".exe")
        if alt_exe.exists():
            return CompileResult(success=True, executable_path=alt_exe)
    else:
        cached_bin = source_path.parent / f"{source_path.stem}.exe"

    cmd_template = COMPILE_COMMANDS[language]
    cmd = [
        arg.format(src=str(source_path), out=str(cached_bin))
        for arg in cmd_template
    ]

    if include_dirs:
        for inc_dir in reversed(include_dirs):
            cmd.insert(1, f"-I{inc_dir}")
    if defines:
        for d in defines:
            cmd.insert(1, f"-D{d}")

    import subprocess
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            # g++ on Windows auto-appends .exe to -o output
            if not cached_bin.exists():
                alt = Path(str(cached_bin) + ".exe")
                if alt.exists():
                    cached_bin = alt
            return CompileResult(success=True, executable_path=cached_bin)
        else:
            return CompileResult(
                success=False,
                errors=result.stderr or result.stdout,
            )
    except subprocess.TimeoutExpired:
        return CompileResult(success=False, errors="Compilation timed out")
    except FileNotFoundError:
        return CompileResult(
            success=False,
            errors=f"Compiler not found: {cmd[0]}. Install it or use a different language.",
        )
