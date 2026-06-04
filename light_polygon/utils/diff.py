from __future__ import annotations

import difflib


def unified_diff(
    a: str, b: str, fromfile: str = "expected", tofile: str = "actual"
) -> str:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff)
