from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from light_polygon.judge.sandbox import run_sandboxed
from light_polygon.problem import layout


@dataclass
class CheckResult:
    verdict: str  # AC, WA, PE, FAIL
    message: str = ""
    score: float = 0.0


# testlib.h exit code mapping (Polygon standard)
TESTLIB_EXIT_CODES = {
    0: "AC",    # _ok
    1: "WA",    # _wa
    2: "PE",    # _pe
    3: "FAIL",  # _fail
    7: "AC",    # _points (partial score, treated as AC for now)
}


def parse_testlib_exit_code(code: int) -> str:
    """Parse testlib checker exit code to verdict."""
    return TESTLIB_EXIT_CODES.get(code, "WA")


def run_testlib_checker(
    checker_exe: Path,
    input_path: Path,
    output_path: Path,
    answer_path: Path,
) -> CheckResult:
    """Run a compiled testlib checker.

    Checker invocation follows Polygon standard:
        ./checker <input_file> <output_file> <answer_file>

    Args:
        checker_exe: Path to compiled checker binary.
        input_path: Path to input file.
        output_path: Path to participant output file.
        answer_path: Path to jury answer file.

    Returns:
        CheckResult with verdict based on testlib exit code.
    """
    result = run_sandboxed(
        [str(checker_exe), str(input_path), str(output_path), str(answer_path)],
        time_limit_ms=10000,
        memory_limit_mb=1024,
    )

    verdict = parse_testlib_exit_code(result.exit_code)

    if verdict == "FAIL":
        return CheckResult(
            verdict="FAIL",
            message=result.stderr.strip() or f"Checker failed with exit code {result.exit_code}",
        )

    if verdict == "AC":
        return CheckResult(verdict="AC", score=1.0)

    # WA or PE
    message = result.stderr.strip() or f"Wrong answer (exit code {result.exit_code})"
    return CheckResult(verdict=verdict, message=message, score=0.0)


# Standard checker names bundled with light-polygon
STANDARD_CHECKERS = [
    "wcmp", "ncmp", "lcmp", "fcmp", "hcmp",
    "rcmp4", "rcmp6", "rcmp9",
    "yesno", "nyesno",
]


def get_standard_checker_path(name: str) -> Path | None:
    """Get path to a standard checker source file bundled with light-polygon."""
    if name not in STANDARD_CHECKERS:
        return None
    vendor_dir = Path(__file__).parent.parent / "vendor" / "checkers"
    path = vendor_dir / f"{name}.cpp"
    if path.exists():
        return path
    return None


def get_checker_source_path(slug: str, checker_name: str) -> Path | None:
    """Get the source path for a problem's checker.

    If checker_name is a standard checker (e.g. 'wcmp', 'ncmp'), return the
    bundled path from vendor/checkers/. If checker_name is 'custom', look for
    checkers/checker.cpp in the problem directory.
    """
    # Check for standard checker
    standard_path = get_standard_checker_path(checker_name)
    if standard_path is not None:
        return standard_path

    # Check for custom checker
    if checker_name == "custom":
        custom_path = layout.problem_dir(slug) / "checkers" / "checker.cpp"
        if custom_path.exists():
            return custom_path
        return None

    # Unknown checker name
    return None
