from __future__ import annotations

from pathlib import Path

import typer

from light_polygon.auth.commands import require_user
from light_polygon.db.connection import init_db, get_connection
from light_polygon.db.models import Problem
from light_polygon.export.packager import export_package
from light_polygon.utils.console import console

export_app = typer.Typer(help="Export problem data", no_args_is_help=True)


@export_app.command()
def package(
    slug: str = typer.Argument(..., help="Problem slug to export"),
    output: str = typer.Option(
        ".", "--output", "-o",
        help="Output path (directory or file; defaults to current directory)",
    ),
    format: str = typer.Option(
        "native", "--format", "-f",
        help="Export format: 'native' (full backup) or 'polygon' (platform-compatible)",
    ),
    all_solutions: bool = typer.Option(
        False, "--all-solutions",
        help="Include all solutions, not just AC-tagged ones",
    ),
) -> None:
    """Package a problem into a zip file."""
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

    if format not in ("native", "polygon"):
        console.print(f"[red]Unknown format '{format}'. Use 'native' or 'polygon'.[/red]")
        raise typer.Exit(1)

    try:
        result = export_package(slug, output, format=format, all_solutions=all_solutions)
        console.print(f"[green]Exported '{slug}' to {result}[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
