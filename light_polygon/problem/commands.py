from __future__ import annotations

import typer
from rich.table import Table

from light_polygon.auth.commands import require_user
from light_polygon.db.connection import init_db, get_connection
from light_polygon.db.models import Problem, User
from light_polygon.problem.manager import ProblemError, ProblemManager
from light_polygon.utils.console import console
from light_polygon.utils.slugify import slugify

problem_app = typer.Typer(help="Problem management", no_args_is_help=True)


@problem_app.command()
def create(
    slug: str = typer.Argument(..., help="Problem slug (URL-safe short name)"),
    title: str = typer.Option("", "--title", "-t", help="Problem title (auto-generated from slug if empty)"),
    time_limit: int = typer.Option(1000, "--tl", "--time-limit", help="Time limit in milliseconds"),
    memory_limit: int = typer.Option(256, "--ml", "--memory-limit", help="Memory limit in megabytes"),
    input_file: str = typer.Option("stdin", "--input-file", help="Input file (stdin or filename)"),
    output_file: str = typer.Option("stdout", "--output-file", help="Output file (stdout or filename)"),
    private: bool = typer.Option(True, "--private/--public", help="Problem visibility"),
) -> None:
    """Create a new problem."""
    username = require_user()
    slug = slugify(slug)
    if not title:
        title = slug.replace("-", " ").title()

    init_db()
    conn = get_connection()
    try:
        user = User.find_by_username(conn, username)
        if user is None:
            console.print("[red]Current user not found in database[/red]")
            raise typer.Exit(1)

        mgr = ProblemManager(conn)
        problem = mgr.create(
            slug=slug, title=title, owner_id=user.id,
            time_limit_ms=time_limit, memory_limit_mb=memory_limit,
            input_file=input_file, output_file=output_file,
            is_private=private,
        )
        console.print(f"[green]Problem '{problem.slug}' created.[/green]")
        console.print(f"  Directory: {get_connection.__module__}")
        from light_polygon.problem.layout import problem_dir
        console.print(f"  Directory: {problem_dir(problem.slug)}")
    except ProblemError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        conn.close()


@problem_app.command("list")
def list_problems(
    mine: bool = typer.Option(False, "--mine", "-m", help="Show only my problems"),
) -> None:
    """List all problems."""
    username = require_user()
    init_db()
    conn = get_connection()
    try:
        if mine:
            user = User.find_by_username(conn, username)
            problems = Problem.list_all(conn, owner_id=user.id) if user else []
        else:
            problems = Problem.list_all(conn)

        if not problems:
            console.print("[dim]No problems found.[/dim]")
            return

        table = Table(title="Problems")
        table.add_column("Slug", style="bold")
        table.add_column("Title")
        table.add_column("TL (ms)")
        table.add_column("ML (MB)")
        table.add_column("Private")
        for p in problems:
            owner = User.find_by_id(conn, p.owner_id)
            owner_name = owner.username if owner else "?"
            table.add_row(
                p.slug, p.title, str(p.time_limit_ms),
                str(p.memory_limit_mb), "yes" if p.is_private else "no",
            )
        console.print(table)
    finally:
        conn.close()


@problem_app.command()
def info(
    slug: str = typer.Argument(..., help="Problem slug"),
) -> None:
    """Show problem details."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        owner = User.find_by_id(conn, problem.owner_id)

        from light_polygon.problem import layout
        from light_polygon.db.models import Solution, TestCase

        solutions = Solution.find_by_problem(conn, problem.id)
        tests = TestCase.find_by_problem(conn, problem.id)

        console.print(f"[heading]Problem: {problem.slug}[/heading]")
        console.print(f"  Title:       {problem.title}")
        console.print(f"  Owner:       {owner.username if owner else '?'}")
        console.print(f"  Time Limit:  {problem.time_limit_ms} ms")
        console.print(f"  Memory Limit:{problem.memory_limit_mb} MB")
        console.print(f"  Input:       {problem.input_file}")
        console.print(f"  Output:      {problem.output_file}")
        console.print(f"  Private:     {'yes' if problem.is_private else 'no'}")
        console.print(f"  Tests:       {len(tests)}")
        console.print(f"  Solutions:   {len(solutions)}")
        console.print(f"  Directory:   {layout.problem_dir(problem.slug)}")
    finally:
        conn.close()


@problem_app.command()
def edit(
    slug: str = typer.Argument(..., help="Problem slug"),
    title: str = typer.Option("", "--title", "-t", help="New title"),
    time_limit: int = typer.Option(0, "--tl", help="New time limit (ms)"),
    memory_limit: int = typer.Option(0, "--ml", help="New memory limit (MB)"),
    private: bool | None = typer.Option(None, "--private/--public", help="Visibility"),
) -> None:
    """Edit problem properties."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        changed = False
        if title:
            problem.title = title
            changed = True
        if time_limit > 0:
            problem.time_limit_ms = time_limit
            changed = True
        if memory_limit > 0:
            problem.memory_limit_mb = memory_limit
            changed = True
        if private is not None:
            problem.is_private = private
            changed = True

        if changed:
            problem.save(conn)
            console.print(f"[green]Problem '{slug}' updated.[/green]")
        else:
            console.print("[dim]No changes specified.[/dim]")
    finally:
        conn.close()


@problem_app.command()
def delete(
    slug: str = typer.Argument(..., help="Problem slug"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a problem and all its data."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        if not force:
            confirm = typer.confirm(f"Delete problem '{slug}' and all its data? This cannot be undone.")
            if not confirm:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)

        mgr = ProblemManager(conn)
        mgr.delete(slug)
        console.print(f"[green]Problem '{slug}' deleted.[/green]")
    except ProblemError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        conn.close()
