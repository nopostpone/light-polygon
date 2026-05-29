from __future__ import annotations

import typer
from rich.table import Table

from light_polygon.auth.commands import require_user
from light_polygon.db.connection import init_db, get_connection
from light_polygon.db.models import Problem, TestCase
from light_polygon.problem import layout
from light_polygon.tests.generator import execute_generators
from light_polygon.tests.manager import TestManager
from light_polygon.tests.toml_config import generate_template_toml, read_tests_toml
from light_polygon.utils.console import console

test_app = typer.Typer(help="Test case management", no_args_is_help=True)


@test_app.command()
def add(
    slug: str = typer.Argument(..., help="Problem slug"),
    input_file: str = typer.Option("", "--input", "-i", help="Input file path (reads stdin if omitted)"),
    answer_file: str = typer.Option("", "--answer", "-a", help="Answer file path"),
    sample: bool = typer.Option(False, "--sample", "-s", help="Mark as sample test"),
    description: str = typer.Option("", "--desc", "-d", help="Test description"),
) -> None:
    """Add a test case to a problem."""
    require_user()
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        if input_file:
            input_data = open(input_file, encoding="utf-8").read()
        else:
            console.print("[dim]Paste input data (Ctrl+D or Ctrl+Z to finish):[/dim]")
            import sys
            input_data = sys.stdin.read()

        answer_data = ""
        if answer_file:
            answer_data = open(answer_file, encoding="utf-8").read()

        mgr = TestManager(conn, slug)
        idx = mgr.next_index(problem.id)
        tc = mgr.add(
            problem.id, idx, input_data, answer_data,
            description=description, is_sample=sample,
        )
        console.print(f"[green]Test #{tc.test_index} added to '{slug}'.[/green]")
    finally:
        conn.close()


@test_app.command("list")
def list_tests(
    slug: str = typer.Argument(..., help="Problem slug"),
    testset: str = typer.Option("tests", "--testset", "-s", help="Test set name"),
) -> None:
    """List test cases for a problem."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        tests = TestCase.find_by_problem(conn, problem.id, testset=testset)
        if not tests:
            console.print(f"[dim]No tests found in testset '{testset}'.[/dim]")
            return

        table = Table(title=f"Tests for '{slug}' ({testset})")
        table.add_column("#", style="dim")
        table.add_column("Description")
        table.add_column("Sample")
        table.add_column("Verified")
        for t in tests:
            table.add_row(
                str(t.test_index), t.description or "-",
                "yes" if t.is_sample else "no",
                "yes" if t.verified else "no",
            )
        console.print(table)
    finally:
        conn.close()


@test_app.command()
def delete(
    slug: str = typer.Argument(..., help="Problem slug"),
    test_index: int = typer.Argument(..., help="Test index to delete"),
) -> None:
    """Delete a test case."""
    require_user()
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        tests = TestCase.find_by_problem(conn, problem.id)
        tc = next((t for t in tests if t.test_index == test_index), None)
        if tc is None:
            console.print(f"[red]Test #{test_index} not found[/red]")
            raise typer.Exit(1)

        mgr = TestManager(conn, slug)
        mgr.delete_files(test_index)
        tc.delete(conn)
        console.print(f"[green]Test #{test_index} deleted from '{slug}'.[/green]")
    finally:
        conn.close()


@test_app.command()
def sample(
    slug: str = typer.Argument(..., help="Problem slug"),
    test_index: int = typer.Argument(..., help="Test index"),
    on: bool = typer.Option(True, "--on/--off", help="Set sample status"),
) -> None:
    """Mark or unmark a test as sample."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)

        tests = TestCase.find_by_problem(conn, problem.id)
        tc = next((t for t in tests if t.test_index == test_index), None)
        if tc is None:
            console.print(f"[red]Test #{test_index} not found[/red]")
            raise typer.Exit(1)

        tc.is_sample = on
        tc.save(conn)
        status = "sample" if on else "not sample"
        console.print(f"[green]Test #{test_index} is now {status}.[/green]")
    finally:
        conn.close()


@test_app.command(name="gen-config")
def gen_config(
    slug: str = typer.Argument(..., help="Problem slug"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing tests.toml"),
) -> None:
    """Create a template tests.toml for the problem."""
    require_user()
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)
    finally:
        conn.close()

    toml_path = layout.tests_toml_path(slug)
    if toml_path.exists() and not force:
        console.print(
            f"[yellow]tests.toml already exists for '{slug}'.[/yellow]\n"
            f"  Use --force to overwrite."
        )
        raise typer.Exit(1)

    template = generate_template_toml(slug)
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    toml_path.write_text(template, encoding="utf-8")
    console.print(f"[green]Created tests.toml for '{slug}'.[/green]")
    console.print(f"  Edit it at: {toml_path}")


@test_app.command()
def generate(
    slug: str = typer.Argument(..., help="Problem slug"),
    generator_name: str = typer.Option(
        "", "--generator", "-g",
        help="Generate only this specific generator",
    ),
) -> None:
    """Generate tests from tests.toml configuration."""
    require_user()
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)
    finally:
        conn.close()

    if not layout.tests_toml_path(slug).exists():
        console.print(
            f"[red]No tests.toml found for '{slug}'.[/red]\n"
            f"  Run 'lp test gen-config {slug}' to create one."
        )
        raise typer.Exit(1)

    tests_toml = read_tests_toml(slug)

    if generator_name:
        tests_toml.generators = [
            g for g in tests_toml.generators if g.name == generator_name
        ]
        if not tests_toml.generators:
            console.print(
                f"[red]Generator '{generator_name}' not found in tests.toml[/red]"
            )
            raise typer.Exit(1)

    console.print(f"[heading]Generating tests for '{slug}'[/heading]")

    count = execute_generators(problem, tests_toml)

    console.print(f"\n[green]Done. {count} test(s) created.[/green]")
