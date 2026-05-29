from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from light_polygon.db.connection import get_connection
from light_polygon.db.models import Invocation, Problem, Solution, TestCase
from light_polygon.judge.checker import BUILTIN_CHECKERS, CheckResult, check_exact
from light_polygon.judge.compiler import CompileResult, compile_source
from light_polygon.judge.sandbox import SandboxResult, run_sandboxed
from light_polygon.problem import layout
from light_polygon.utils.console import console


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


def run_solution_on_test(
    problem: Problem,
    solution: Solution,
    test: TestCase,
    executable: Path,
    checker_name: str = "exact",
) -> JudgeResult:
    input_data = layout.test_input_path(problem.slug, test.test_index).read_text(encoding="utf-8")
    answer_path = layout.test_answer_path(problem.slug, test.test_index)

    lang = solution.language
    if lang == "python":
        cmd = ["python", str(executable)]
    elif lang in ("cpp", "c"):
        cmd = [str(executable)]
    elif lang == "java":
        cmd = ["java", "-cp", str(executable.parent), executable.stem]
    else:
        cmd = ["python", str(executable)]

    sandbox_result = run_sandboxed(
        cmd,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        stdin_data=input_data,
    )

    verdict = sandbox_result.verdict
    score = 0.0
    error = sandbox_result.error

    if verdict == "AC":
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(sandbox_result.stdout)
            output_path = Path(f.name)

        try:
            checker_fn = BUILTIN_CHECKERS.get(checker_name, check_exact)
            check_result = checker_fn(
                layout.test_input_path(problem.slug, test.test_index),
                output_path,
                answer_path,
            )
            verdict = check_result.verdict
            score = check_result.score
            error = check_result.message
        finally:
            output_path.unlink(missing_ok=True)

    output_hash = hashlib.sha256(sandbox_result.stdout.encode("utf-8", errors="replace")).hexdigest()

    conn = get_connection()
    try:
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
    finally:
        conn.close()

    return JudgeResult(
        solution=solution,
        test=test,
        verdict=verdict,
        score=score,
        cpu_time_ms=sandbox_result.cpu_time_ms,
        wall_time_ms=sandbox_result.wall_time_ms,
        memory_kb=sandbox_result.memory_kb,
        error=error,
        invocation=invocation,
    )


def judge_all(
    problem: Problem,
    solutions: list[Solution] | None = None,
    tests: list[TestCase] | None = None,
    checker_name: str = "exact",
) -> JudgeSummary:
    if solutions is None:
        conn = get_connection()
        try:
            solutions = Solution.find_by_problem(conn, problem.id)
        finally:
            conn.close()

    if tests is None:
        conn = get_connection()
        try:
            tests = TestCase.find_by_problem(conn, problem.id, testset="tests")
        finally:
            conn.close()

    if not solutions or not tests:
        return JudgeSummary(problem=problem)

    summary = JudgeSummary(problem=problem)
    compiled: dict[str, Path] = {}

    total = len(solutions) * len(tests)
    import rich.progress

    with rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.BarColumn(),
        rich.progress.TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Judging...", total=total)

        for sol in solutions:
            if sol.name in summary.compile_errors:
                continue

            if sol.name not in compiled:
                lang = sol.language
                sol_path = layout.solutions_dir(problem.slug) / sol.source_path.split("/")[-1]
                if not sol_path.exists():
                    sol_path = layout.problem_dir(problem.slug) / sol.source_path

                compile_result = compile_source(sol_path, lang)
                if not compile_result.success:
                    summary.compile_errors[sol.name] = compile_result.errors
                    for t in tests:
                        summary.results.append(JudgeResult(
                            solution=sol, test=t, verdict="CE",
                            error=compile_result.errors,
                        ))
                    progress.update(task, advance=len(tests))
                    continue
                compiled[sol.name] = compile_result.executable_path

            for tc in tests:
                result = run_solution_on_test(
                    problem, sol, tc, compiled[sol.name], checker_name,
                )
                summary.results.append(result)
                progress.update(task, advance=1)

    return summary
