from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import sqlite3

from light_polygon.db.models import Invocation, Problem, Solution, TestCase
from light_polygon.judge.checker import get_checker_source_path, run_testlib_checker
from light_polygon.judge.compiler import CompileResult, compile_source
from light_polygon.judge.sandbox import SandboxResult, run_sandboxed
from light_polygon.problem import layout


@dataclass
class JudgeResult:
    solution: Solution
    test: TestCase
    verdict: str
    score: float = 0.0
    cpu_time_ms: int = 0
    wall_time_ms: int = 0
    memory_kb: int = 0
    error: str = ""
    invocation: Invocation | None = None


@dataclass
class JudgeSummary:
    problem: Problem
    results: list[JudgeResult] = field(default_factory=list)
    compile_errors: dict[str, str] = field(default_factory=dict)

    @property
    def by_solution(self) -> dict[str, list[JudgeResult]]:
        groups: dict[str, list[JudgeResult]] = {}
        for r in self.results:
            groups.setdefault(r.solution.name, []).append(r)
        return groups


def _compile_checker(problem: Problem, checker_name: str) -> CompileResult:
    """Compile the checker for a problem. Returns CompileResult."""
    source_path = get_checker_source_path(problem.slug, checker_name)
    if source_path is None:
        return CompileResult(success=False, errors=f"Checker source not found for '{checker_name}'")

    # Include vendor/testlib for standard checkers, and problem files/ for custom
    include_dirs = [str(Path(__file__).parent.parent / "vendor")]
    problem_files = layout.problem_dir(problem.slug) / "files"
    if problem_files.exists():
        include_dirs.append(str(problem_files))

    return compile_source(source_path, "cpp", include_dirs=include_dirs)


def _run_solution(problem: Problem, solution: Solution, test: TestCase, executable: Path) -> SandboxResult:
    input_path = layout.test_input_path(problem.slug, test.test_index)
    input_data = input_path.read_text(encoding="utf-8")

    lang = solution.language
    if lang == "python":
        cmd = ["python", str(executable)]
    elif lang in ("cpp", "c"):
        cmd = [str(executable)]
    elif lang == "java":
        cmd = ["java", "-cp", str(executable.parent), executable.stem]
    else:
        cmd = ["python", str(executable)]

    return run_sandboxed(
        cmd,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        stdin_data=input_data,
    )


def judge_solution(
    conn: sqlite3.Connection,
    problem: Problem,
    solution: Solution,
    tests: list[TestCase],
    checker_name: str = "wcmp",
    on_test_judged: Callable | None = None,
) -> list[JudgeResult]:
    """Judge a single solution against all tests.

    Args:
        conn: Database connection (managed by caller via db_transaction).
        problem: The problem being judged.
        solution: The solution to judge.
        tests: List of test cases to run against.
        checker_name: Checker identifier (e.g. 'wcmp', 'ncmp', 'custom').
        on_test_judged: Optional callback invoked after each test is judged.

    Returns:
        List of JudgeResult, one per test case.
    """
    results: list[JudgeResult] = []

    # Compile checker once
    checker_result = _compile_checker(problem, checker_name)
    if not checker_result.success:
        error = f"Checker '{checker_name}' compilation failed: {checker_result.errors}"
        for test in tests:
            results.append(JudgeResult(
                solution=solution, test=test, verdict="CE", error=error,
            ))
        return results

    checker_exe = checker_result.executable_path

    # Compile solution
    sol_path = layout.solutions_dir(problem.slug) / solution.source_path.split("/")[-1]
    if not sol_path.exists():
        sol_path = layout.problem_dir(problem.slug) / solution.source_path

    compile_result = compile_source(sol_path, solution.language or "cpp")
    if not compile_result.success:
        error = compile_result.errors
        for test in tests:
            results.append(JudgeResult(
                solution=solution, test=test, verdict="CE", error=error,
            ))
        return results

    sol_executable = compile_result.executable_path
    assert sol_executable is not None

    for test in tests:
        sandbox_result = _run_solution(problem, solution, test, sol_executable)
        verdict = sandbox_result.verdict
        score = 0.0
        error = sandbox_result.error

        if verdict == "AC" and checker_exe is not None:
            input_path = layout.test_input_path(problem.slug, test.test_index)
            answer_path = layout.test_answer_path(problem.slug, test.test_index)

            # Write output to temp file for checker.
            # Use binary mode to avoid Windows text mode \n -> \r\n conversion,
            # which confuses testlib checkers.
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
                f.write(sandbox_result.stdout.encode("utf-8"))
                output_path = Path(f.name)

            try:
                check_result = run_testlib_checker(
                    checker_exe, input_path, output_path, answer_path
                )
                verdict = check_result.verdict
                score = check_result.score
                error = check_result.message
            finally:
                output_path.unlink(missing_ok=True)

        output_hash = hashlib.sha256(
            sandbox_result.stdout.encode("utf-8", errors="replace")
        ).hexdigest()

        assert problem.id is not None
        assert solution.id is not None
        assert test.id is not None
        invocation = Invocation.create(
            conn,
            problem_id=problem.id,
            solution_id=solution.id,
            test_id=test.id,
            verdict=verdict,
            score=score,
            cpu_time_ms=sandbox_result.cpu_time_ms,
            wall_time_ms=sandbox_result.wall_time_ms,
            memory_kb=sandbox_result.memory_kb,
            exit_code=sandbox_result.exit_code,
            output_hash=output_hash,
            error_text=error[:1000] if error else "",
        )

        results.append(JudgeResult(
            solution=solution,
            test=test,
            verdict=verdict,
            score=score,
            cpu_time_ms=sandbox_result.cpu_time_ms,
            wall_time_ms=sandbox_result.wall_time_ms,
            memory_kb=sandbox_result.memory_kb,
            error=error,
            invocation=invocation,
        ))
        if on_test_judged is not None:
            on_test_judged()

    return results


def judge_all(
    conn: sqlite3.Connection,
    problem: Problem,
    solutions: list[Solution] | None = None,
    tests: list[TestCase] | None = None,
    checker_name: str = "wcmp",
    on_test_judged: Callable | None = None,
) -> JudgeSummary:
    """Judge all solutions against all tests.

    Args:
        conn: Database connection (managed by caller).
        problem: The problem being judged.
        solutions: Solutions to judge (defaults to all problem solutions).
        tests: Test cases to use (defaults to 'tests' testset).
        checker_name: Checker identifier.
        on_test_judged: Optional callback invoked after each test is judged.

    Returns:
        JudgeSummary with all results grouped by solution.
    """
    if solutions is None:
        solutions = Solution.find_by_problem(conn, problem.id)
    if tests is None:
        tests = TestCase.find_by_problem(conn, problem.id, testset="tests")

    summary = JudgeSummary(problem=problem)

    if not solutions or not tests:
        return summary

    for sol in solutions:
        results = judge_solution(
            conn, problem, sol, tests, checker_name,
            on_test_judged=on_test_judged,
        )
        summary.results.extend(results)
        # Detect compile errors (all CE)
        if results and all(r.verdict == "CE" for r in results):
            summary.compile_errors[sol.name] = results[0].error or "Compilation error"

    return summary
