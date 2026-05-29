from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from light_polygon.utils.diff import unified_diff


@dataclass
class CheckResult:
    verdict: str  # AC, WA, PE
    message: str = ""
    score: float = 0.0


def check_exact(input_path: Path, output_path: Path, answer_path: Path) -> CheckResult:
    """Byte-for-byte comparison."""
    try:
        output_data = output_path.read_bytes()
        answer_data = answer_path.read_bytes()
    except FileNotFoundError as e:
        return CheckResult(verdict="WA", message=f"Missing file: {e}")

    if output_data == answer_data:
        return CheckResult(verdict="AC", score=1.0)
    else:
        diff = unified_diff(
            answer_data.decode("utf-8", errors="replace"),
            output_data.decode("utf-8", errors="replace"),
        )
        return CheckResult(verdict="WA", message=diff, score=0.0)


def check_tokens(input_path: Path, output_path: Path, answer_path: Path,
                 case_insensitive: bool = False) -> CheckResult:
    """Token-wise comparison (whitespace-agnostic)."""
    try:
        output_text = output_path.read_text(encoding="utf-8")
        answer_text = answer_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        return CheckResult(verdict="WA", message=f"Missing file: {e}")

    out_tokens = output_text.split()
    ans_tokens = answer_text.split()

    if len(out_tokens) != len(ans_tokens):
        diff = unified_diff(answer_text, output_text)
        return CheckResult(
            verdict="WA",
            message=f"Token count mismatch: {len(out_tokens)} vs {len(ans_tokens)}\n{diff}",
            score=0.0,
        )

    for i, (a, b) in enumerate(zip(ans_tokens, out_tokens)):
        if case_insensitive:
            a, b = a.lower(), b.lower()
        if a != b:
            diff = unified_diff(answer_text, output_text)
            return CheckResult(
                verdict="WA",
                message=f"Token {i + 1} mismatch: expected '{a}', got '{b}'\n{diff}",
                score=0.0,
            )

    return CheckResult(verdict="AC", score=1.0)


def check_fcmp(input_path: Path, output_path: Path, answer_path: Path,
               epsilon: float = 1e-6) -> CheckResult:
    """Floating-point token comparison with tolerance."""
    try:
        output_text = output_path.read_text(encoding="utf-8")
        answer_text = answer_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        return CheckResult(verdict="WA", message=f"Missing file: {e}")

    out_tokens = output_text.split()
    ans_tokens = answer_text.split()

    if len(out_tokens) != len(ans_tokens):
        diff = unified_diff(answer_text, output_text)
        return CheckResult(
            verdict="WA",
            message=f"Token count mismatch: {len(out_tokens)} vs {len(ans_tokens)}\n{diff}",
        )

    for i, (a_str, b_str) in enumerate(zip(ans_tokens, out_tokens)):
        try:
            a_val = float(a_str)
            b_val = float(b_str)
            if abs(a_val - b_val) > epsilon and abs(a_val - b_val) / max(1.0, abs(a_val)) > epsilon:
                return CheckResult(
                    verdict="WA",
                    message=f"Token {i + 1}: expected {a_str}, got {b_str} (diff: {abs(a_val - b_val):.2e})",
                )
        except ValueError:
            if a_str != b_str:
                return CheckResult(
                    verdict="WA",
                    message=f"Token {i + 1}: expected '{a_str}', got '{b_str}'",
                )

    return CheckResult(verdict="AC", score=1.0)


BUILTIN_CHECKERS = {
    "exact": check_exact,
    "tokens": check_tokens,
    "fcmp": check_fcmp,
}
