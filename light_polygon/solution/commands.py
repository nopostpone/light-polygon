from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from light_polygon.auth.commands import require_user
from light_polygon.db.connection import init_db, get_connection
from light_polygon.db.models import Problem, Solution
from light_polygon.solution.manager import add_solution_file, language_from_path
from light_polygon.utils.console import console

solution_app = typer.Typer(help="Solution management", no_args_is_help=True)

VALID_TAGS = ["AC", "WA", "TLE", "MLE", "RTE", "CE", "RJ", "MANUAL"]


@solution_app.command()
def add(
    slug: str = typer.Argument(..., help="Problem slug"),
    file: str = typer.Argument(..., help="Path to solution source file"),
    tag: str = typer.Option("AC", "--tag", "-t", help="Expected verdict (AC, WA, TLE, MLE, RTE)"),
    name: str = typer.Option("", "--as", help="Custom name for the solution"),
) -> None:
    """Add a solution to a problem."""
    require_user()
    if tag not in VALID_TAGS:
        console.print(f"[red]Invalid tag '{tag}'. Valid tags: {', '.join(VALID_TAGS)}[/red]")
        raise typer.Exit(1)

    source_path = Path(file)
    if not source_path.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        sol_name = name if name else source_path.name
        lang = language_from_path(source_path)

        _ = add_solution_file(slug, sol_name, source_path)
        rel_path = f"solutions/{sol_name}"

        Solution.create(
            conn, problem_id=problem.id, name=sol_name,
            language=lang, source_path=rel_path, tag=tag,
        )
        conn.commit()
        console.print(f"[green]Solution '{sol_name}' ({lang}, {tag}) added to '{slug}'.[/green]")
    finally:
        conn.close()


@solution_app.command("list")
def list_solutions(
    slug: str = typer.Argument(..., help="Problem slug"),
) -> None:
    """List all solutions for a problem."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        solutions = Solution.find_by_problem(conn, problem.id)
        if not solutions:
            console.print("[dim]No solutions added yet.[/dim]")
            return

        table = Table(title=f"Solutions for '{slug}'")
        table.add_column("Name", style="bold")
        table.add_column("Language")
        table.add_column("Tag")
        for s in solutions:
            verdict_style = {
                "AC": "verdict.ac", "WA": "verdict.wa", "TLE": "verdict.tle",
                "MLE": "verdict.mle", "RTE": "verdict.rte", "CE": "verdict.ce",
            }.get(s.tag, "")
            table.add_row(s.name, s.language, f"[{verdict_style}]{s.tag}[/{verdict_style}]")
        console.print(table)
    finally:
        conn.close()


@solution_app.command()
def delete(
    slug: str = typer.Argument(..., help="Problem slug"),
    name: str = typer.Argument(..., help="Solution name"),
) -> None:
    """Delete a solution."""
    require_user()
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        solutions = Solution.find_by_problem(conn, problem.id)
        sol = next((s for s in solutions if s.name == name), None)
        if sol is None:
            console.print(f"[red]Solution '{name}' not found[/red]")
            raise typer.Exit(1)

        sol.delete(conn)
        conn.commit()
        console.print(f"[green]Solution '{name}' deleted from '{slug}'.[/green]")
    finally:
        conn.close()


@solution_app.command()
def tag(
    slug: str = typer.Argument(..., help="Problem slug"),
    name: str = typer.Argument(..., help="Solution name"),
    new_tag: str = typer.Argument(..., help="New tag (AC, WA, TLE, MLE, RTE, CE, MANUAL)"),
) -> None:
    """Change the expected verdict tag of a solution."""
    if new_tag not in VALID_TAGS:
        console.print(f"[red]Invalid tag '{new_tag}'. Valid tags: {', '.join(VALID_TAGS)}[/red]")
        raise typer.Exit(1)

    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        solutions = Solution.find_by_problem(conn, problem.id)
        sol = next((s for s in solutions if s.name == name), None)
        if sol is None:
            console.print(f"[red]Solution '{name}' not found[/red]")
            raise typer.Exit(1)

        sol.tag = new_tag
        sol.save(conn)
        conn.commit()
        console.print(f"[green]Solution '{name}' tag updated to '{new_tag}'.[/green]")
    finally:
        conn.close()
