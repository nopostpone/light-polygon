from __future__ import annotations

import shutil

import typer
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from light_polygon.auth.commands import require_user
from light_polygon.db.context import db_transaction
from light_polygon.db.models import Problem, Solution, TestCase
from light_polygon.judge.service import judge_all
from light_polygon.utils.console import console

judge_app = typer.Typer(help="Judging and evaluation", no_args_is_help=True)

VERDICT_STYLES = {
    "AC": "[verdict.ac]AC[/verdict.ac]",
    "WA": "[verdict.wa]WA[/verdict.wa]",
    "TLE": "[verdict.tle]TLE[/verdict.tle]",
    "MLE": "[verdict.mle]MLE[/verdict.mle]",
    "RTE": "[verdict.rte]RTE[/verdict.rte]",
    "CE": "[verdict.ce]CE[/verdict.ce]",
    "PE": "[verdict.pe]PE[/verdict.pe]",
    "FAIL": "[verdict.fail]FAIL[/verdict.fail]",
}


def _format_verdict(v: str) -> str:
    return VERDICT_STYLES.get(v, v)


def _require_gpp() -> None:
    if not shutil.which("g++"):
        console.print(
            "[red]g++ not found on PATH.[/red]\n"
            "  Please install a C++ compiler:\n"
            "    Ubuntu/Debian: sudo apt install g++\n"
            "    macOS:         xcode-select --install\n"
            "    Windows:       Install MSYS2 or MinGW-w64"
        )
        raise typer.Exit(1)


@judge_app.command()
def run(
    slug: str = typer.Argument(..., help="Problem slug"),
    solution_name: str = typer.Option("", "--solution", "-s", help="Judge only this solution"),
    test_index: int = typer.Option(0, "--test", "-t", help="Judge only this test"),
    checker: str = typer.Option("wcmp", "--checker", "-c", help="Checker name (wcmp, ncmp, lcmp, fcmp, rcmp4/6/9, yesno, nyesno, custom)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output for failures"),
) -> None:
    """Judge all solutions on all tests."""
    require_user()
    _require_gpp()

    with db_transaction() as conn:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        solutions = Solution.find_by_problem(conn, problem.id)
        if solution_name:
            solutions = [s for s in solutions if s.name == solution_name]
            if not solutions:
                console.print(f"[red]Solution '{solution_name}' not found[/red]")
                raise typer.Exit(1)

        tests = TestCase.find_by_problem(conn, problem.id, testset="tests")
        if test_index > 0:
            tests = [t for t in tests if t.test_index == test_index]
            if not tests:
                console.print(f"[red]Test #{test_index} not found[/red]")
                raise typer.Exit(1)

        if not solutions:
            console.print("[red]No solutions to judge.[/red]")
            return
        if not tests:
            console.print("[red]No tests to judge.[/red]")
            return

        console.print(f"[heading]Judging '{slug}'[/heading]")
        console.print(f"  Solutions: {len(solutions)}  Tests: {len(tests)}  Checker: {checker}")
        console.print()

        total_tests = len(solutions) * len(tests)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Judging...", total=total_tests)

            def _advance():
                progress.advance(task)

            summary = judge_all(
                conn, problem, solutions, tests,
                checker_name=checker, on_test_judged=_advance,
            )

    # Compile errors
    for sol_name, err in summary.compile_errors.items():
        console.print(Panel(err, title=f"[red]Compile Error: {sol_name}[/red]", border_style="red"))

    # Summary table
    table = Table(title="Results")
    table.add_column("Solution")
    table.add_column("Test")
    table.add_column("Verdict")
    table.add_column("Time")
    table.add_column("Memory")

    for r in summary.results:
        time_str = f"{r.wall_time_ms}ms" if r.wall_time_ms else "-"
        mem_str = f"{r.memory_kb}KB" if r.memory_kb else "-"
        table.add_row(
            r.solution.name,
            f"#{r.test.test_index}",
            _format_verdict(r.verdict),
            time_str,
            mem_str,
        )

    console.print(table)

    # Aggregate
    console.print()
    agg_table = Table(title="Summary by Solution")
    agg_table.add_column("Solution")
    agg_table.add_column("Tag")
    agg_table.add_column("AC")
    agg_table.add_column("WA")
    agg_table.add_column("TLE")
    agg_table.add_column("RTE")
    agg_table.add_column("Total")

    by_sol = summary.by_solution
    for sol in solutions:
        results = by_sol.get(sol.name, [])
        counts = {"AC": 0, "WA": 0, "TLE": 0, "RTE": 0, "MLE": 0, "CE": 0, "PE": 0, "FAIL": 0}
        for r in results:
            counts[r.verdict] = counts.get(r.verdict, 0) + 1
        agg_table.add_row(
            sol.name,
            sol.tag,
            str(counts["AC"]),
            str(counts["WA"]),
            str(counts["TLE"]),
            str(counts["RTE"]),
            str(len(results)),
        )

    console.print(agg_table)

    # Show mismatches
    for sol in solutions:
        results = by_sol.get(sol.name, [])
        if not results:
            continue
        has_wrong = any(r.verdict != sol.tag for r in results if r.verdict != "CE")
        if has_wrong and sol.tag != "MANUAL":
            console.print(f"  [yellow]Solution '{sol.name}' tagged {sol.tag} but got unexpected verdicts[/yellow]")

    # Verbose output for failures
    if verbose:
        for r in summary.results:
            if r.verdict not in ("AC",):
                console.print()
                console.print(Panel(
                    r.error or "(no details)",
                    title=f"{r.solution.name} / Test #{r.test.test_index} / {r.verdict}",
                    border_style="red",
                ))


@judge_app.command()
def history(
    slug: str = typer.Argument(..., help="Problem slug"),
    solution_name: str = typer.Option("", "--solution", "-s", help="Filter by solution"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of results to show"),
) -> None:
    """Show recent judging history."""
    with db_transaction() as conn:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        rows = conn.execute(
            """SELECT i.*, s.name as sol_name, t.test_index
               FROM invocations i
               JOIN solutions s ON i.solution_id = s.id
               JOIN tests t ON i.test_id = t.id
               WHERE i.problem_id = ?
               ORDER BY i.judged_at DESC
               LIMIT ?""",
            (problem.id, limit),
        ).fetchall()

        if not rows:
            console.print("[dim]No judging history.[/dim]")
            return

        table = Table(title=f"Judging History for '{slug}'")
        table.add_column("When", style="dim")
        table.add_column("Solution")
        table.add_column("Test")
        table.add_column("Verdict")
        table.add_column("Time")
        table.add_column("Memory")

        for r in rows:
            time_str = f"{r['wall_time_ms']}ms" if r["wall_time_ms"] else "-"
            mem_str = f"{r['memory_kb']}KB" if r["memory_kb"] else "-"
            table.add_row(
                r["judged_at"][:19] if r["judged_at"] else "-",
                r["sol_name"],
                f"#{r['test_index']}",
                _format_verdict(r["verdict"]),
                time_str,
                mem_str,
            )

        console.print(table)
