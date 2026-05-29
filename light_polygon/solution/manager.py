from __future__ import annotations

import shutil
from pathlib import Path

from light_polygon.problem import layout


def language_from_path(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    lang_map = {
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".py": "python",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".js": "javascript",
        ".ts": "typescript",
        ".kt": "kotlin",
    }
    return lang_map.get(ext, "unknown")


def add_solution_file(slug: str, name: str, source_path: str | Path) -> Path:
    src = Path(source_path)
    dest = layout.solutions_dir(slug) / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest
