from __future__ import annotations

import hashlib
from pathlib import Path

from light_polygon.config import get_config
from light_polygon.db.connection import get_connection
from light_polygon.db.models import Problem, Solution
from light_polygon.judge.compiler import CompileResult, compile_source
from light_polygon.judge.sandbox import SandboxResult, run_sandboxed
from light_polygon.problem import layout
from light_polygon.solution.manager import language_from_path
from light_polygon.tests.manager import TestManager
from light_polygon.tests.toml_config import GeneratorConfig, GeneratorInvocation, ManualTest, TestsToml
from light_polygon.utils.console import console

GENERATOR_TIME_LIMIT_MS = 30000
GENERATOR_MEMORY_LIMIT_MB = 1024
ANSWER_TIME_LIMIT_MS = 5000
ANSWER_MEMORY_LIMIT_MB = 1024
VALIDATOR_TIME_LIMIT_MS = 10000
VALIDATOR_MEMORY_LIMIT_MB = 512


def get_testlib_include_dir() -> Path:
    return Path(__file__).parent.parent / "vendor"


def get_gen_cache_dir() -> Path:
    d = get_config().data_dir / "cache" / "generators"
    d.mkdir(parents=True, exist_ok=True)
    return d


def compile_generator(slug: str, gen_config: GeneratorConfig) -> CompileResult:
    source_path = layout.generators_dir(slug) / gen_config.source
    if not source_path.exists():
        return CompileResult(success=False, errors=f"Generator source not found: {source_path}")
    return compile_source(
        source_path, "cpp",
        cache_dir=get_gen_cache_dir(),
        include_dirs=[str(get_testlib_include_dir())],
        defines=["FOR_LINUX"],
    )


def run_generator(
    executable: Path, args: list[str], seed: int, working_dir: Path,
) -> SandboxResult:
    cmd = [str(executable)] + args + ["--seed", str(seed)]
    return run_sandboxed(
        cmd,
        time_limit_ms=GENERATOR_TIME_LIMIT_MS,
        memory_limit_mb=GENERATOR_MEMORY_LIMIT_MB,
        working_dir=working_dir,
    )


def compile_validator(slug: str) -> CompileResult | None:
    source_path = layout.files_dir(slug) / "validator.cpp"
    if not source_path.exists():
        return None
    return compile_source(
        source_path, "cpp",
        cache_dir=get_gen_cache_dir(),
        include_dirs=[str(get_testlib_include_dir())],
        defines=["FOR_LINUX"],
    )


def validate_input(executable: Path, input_data: str) -> tuple[bool, str]:
    """Run validator on test input. Returns (passed, error_message)."""
    result = run_sandboxed(
        [str(executable)],
        time_limit_ms=VALIDATOR_TIME_LIMIT_MS,
        memory_limit_mb=VALIDATOR_MEMORY_LIMIT_MB,
        stdin_data=input_data,
    )
    if result.exit_code == 0:
        return True, ""
    # testlib.h on Windows with MSYS2 g++ may crash on exit (0xC0000005)
    # after producing correct validation result.
    # Accept as pass if stderr is empty (no validation error message).
    if result.exit_code == 0xC0000005 and not result.stderr.strip():
        return True, ""
    msg = result.stderr.strip() or f"Validator exited with code {result.exit_code}"
    return False, msg


def _find_solution(problem: Problem, answer_by: str) -> Solution | None:
    conn = get_connection()
    try:
        sols = Solution.find_by_problem(conn, problem.id)
    finally:
        conn.close()
    for s in sols:
        if s.name == answer_by:
            return s
    return None


def _resolve_solution_path(problem: Problem, sol: Solution) -> Path | None:
    sol_path = layout.solutions_dir(problem.slug) / sol.source_path.split("/")[-1]
    if sol_path.exists():
        return sol_path
    sol_path = layout.problem_dir(problem.slug) / sol.source_path
    if sol_path.exists():
        return sol_path
    return None


def generate_answer(
    problem: Problem, answer_by: str, input_data: str,
) -> tuple[str, str | None]:
    """Run reference solution to produce answer. Returns (answer, error)."""
    if not answer_by:
        return "", None

    sol = _find_solution(problem, answer_by)
    if sol is None:
        return "", f"Solution '{answer_by}' not found for problem '{problem.slug}'"

    sol_path = _resolve_solution_path(problem, sol)
    if sol_path is None:
        return "", f"Solution file not found: {sol.source_path}"

    lang = sol.language or language_from_path(sol_path)
    compile_result = compile_source(sol_path, lang)
    if not compile_result.success:
        return "", f"Compilation failed for '{answer_by}': {compile_result.errors}"

    executable = compile_result.executable_path
    if lang == "python":
        cmd = ["python", str(executable)]
    elif lang in ("cpp", "c"):
        cmd = [str(executable)]
    elif lang == "java":
        cmd = ["java", "-cp", str(executable.parent), executable.stem]
    else:
        cmd = ["python", str(executable)]

    result = run_sandboxed(
        cmd,
        time_limit_ms=ANSWER_TIME_LIMIT_MS,
        memory_limit_mb=ANSWER_MEMORY_LIMIT_MB,
        stdin_data=input_data,
    )

    if result.verdict != "AC":
        return "", f"Answer solution '{answer_by}' failed: {result.verdict} (exit {result.exit_code})"

    return result.stdout, None


def _make_seed(gen_name: str, inv_idx: int, i: int) -> int:
    base = int(hashlib.md5(gen_name.encode()).hexdigest()[:8], 16) % 900000 + 100000
    return base + inv_idx * 100000 + i


def execute_generators(problem: Problem, tests_toml: TestsToml) -> int:
    created = 0
    conn = get_connection()
    try:
        mgr = TestManager(conn, problem.slug)
        working_dir = layout.problem_dir(problem.slug)

        # ── Compile validator if present ──────────────────────────────
        validator_exe: Path | None = None
        val_result = compile_validator(problem.slug)
        if val_result is not None:
            if val_result.success:
                validator_exe = val_result.executable_path
                console.print(f"[bold]Validator:[/bold] validator.cpp")
            else:
                console.print(f"[red]Validator compile error:[/red] {val_result.errors}")
                return 0

        # ── Manual tests ─────────────────────────────────────────────
        for mt in tests_toml.tests:
            idx = mt.index if mt.index > 0 else mgr.next_index(problem.id)
            if validator_exe and mt.input.strip():
                ok, msg = validate_input(validator_exe, mt.input)
                if not ok:
                    console.print(
                        f"  [yellow]Skip manual test #{idx}: validation failed[/yellow]"
                    )
                    console.print(f"    [dim]{msg[:200]}[/dim]")
                    continue
            mgr.add(
                problem.id, idx, mt.input, mt.answer,
                description=mt.description, is_sample=mt.is_sample,
                generator="manual",
            )
            console.print(f"  [dim]Manual test #{idx}[/dim] {mt.description or ''}")
            created += 1

        # ── Generated tests ──────────────────────────────────────────
        for gen in tests_toml.generators:
            console.print(f"[bold]Generator: {gen.name}[/bold] ({gen.source})")

            compile_result = compile_generator(problem.slug, gen)
            if not compile_result.success:
                console.print(f"  [red]Compile error:[/red] {compile_result.errors}")
                continue

            exe = compile_result.executable_path

            for inv_idx, inv in enumerate(gen.invocations):
                for i in range(inv.count):
                    seed = _make_seed(gen.name, inv_idx, i)
                    desc = inv.description or f"{gen.name} (seed={seed})"

                    result = run_generator(exe, inv.args, seed, working_dir)
                    # testlib.h on Windows with MSYS2 g++ may crash on exit
                    # (0xC0000005) after producing correct output.
                    # Accept output if stdout is non-empty, even on non-zero exit.
                    if not result.stdout.strip() and result.verdict != "AC":
                        console.print(
                            f"  [yellow]Skip (seed={seed}): {result.verdict}[/yellow]"
                        )
                        if result.stderr:
                            console.print(f"    [dim]{result.stderr[:200]}[/dim]")
                        continue

                    if result.verdict != "AC" and result.stdout.strip():
                        console.print(
                            f"  [dim]Generator exited with {result.verdict} but produced output[/dim]"
                        )

                    input_data = result.stdout

                    if validator_exe:
                        ok, msg = validate_input(validator_exe, input_data)
                        if not ok:
                            console.print(
                                f"  [yellow]Skip (seed={seed}): validation failed[/yellow]"
                            )
                            console.print(f"    [dim]{msg[:200]}[/dim]")
                            continue

                    answer_data, error = generate_answer(
                        problem, inv.answer_by, input_data,
                    )
                    if error:
                        console.print(f"  [yellow]Skip (seed={seed}): {error}[/yellow]")
                        continue

                    idx = mgr.next_index(problem.id)
                    gen_label = f"{gen.name}[{inv_idx}]:{seed}"
                    mgr.add(
                        problem.id, idx, input_data, answer_data,
                        testset=gen.testset, description=desc,
                        generator=gen_label,
                    )
                    console.print(
                        f"  [green]Test #{idx}[/green] {desc}"
                        + (f" [dim](answer by {inv.answer_by})[/dim]" if inv.answer_by else "")
                    )
                    created += 1
    finally:
        conn.close()

    return created
