from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

import typer

from light_polygon.auth.commands import require_user
from light_polygon.db.connection import init_db, get_connection
from light_polygon.db.models import Problem
from light_polygon.problem import layout
from light_polygon.statement.renderer import (
    render_html_page,
    render_latex_page,
    render_terminal,
)
from light_polygon.utils.console import console

statement_app = typer.Typer(help="Statement management", no_args_is_help=True)


def _open_editor(filepath: Path) -> None:
    """Open a file in the user's preferred text editor."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        subprocess.run([editor, str(filepath)], check=False)
    elif platform.system() == "Windows":
        os.startfile(str(filepath))
    else:
        # Fallback: try common editors
        for cmd in [["nano", str(filepath)], ["vi", str(filepath)]]:
            try:
                subprocess.run(cmd, check=True)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        console.print("[yellow]No editor found. Set $EDITOR or edit the file manually:[/yellow]")
        console.print(f"  {filepath}")


@statement_app.command()
def edit(
    slug: str = typer.Argument(..., help="Problem slug"),
) -> None:
    """Open the problem statement in your editor."""
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

    st_path = layout.statement_path(slug)
    if not st_path.exists():
        st_path.parent.mkdir(parents=True, exist_ok=True)
        st_path.write_text(
            f"# {problem.title}\n\n"
            "## Description\n\n\n\n"
            "## Input\n\n\n\n"
            "## Output\n\n\n\n"
            "## Examples\n\n"
            "```\nInput:\n\nOutput:\n```\n\n"
            "## Notes\n\n",
            encoding="utf-8",
        )

    console.print(f"[dim]Opening {st_path}...[/dim]")
    _open_editor(st_path)


@statement_app.command()
def preview(
    slug: str = typer.Argument(..., help="Problem slug"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw markdown without terminal rendering"),
) -> None:
    """Preview the problem statement in the terminal."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)
    finally:
        conn.close()

    st_path = layout.statement_path(slug)
    if not st_path.exists():
        console.print("[yellow]No statement file found. Run 'lp statement edit' first.[/yellow]")
        raise typer.Exit(1)

    md_text = st_path.read_text(encoding="utf-8")

    if raw:
        console.print(md_text)
    else:
        rendered = render_terminal(md_text)
        from rich.markdown import Markdown
        md = Markdown(rendered)
        console.print(md)


@statement_app.command()
def export(
    slug: str = typer.Argument(..., help="Problem slug"),
    fmt: str = typer.Option("html", "--format", "-f", help="Output format: html, tex"),
    output: str = typer.Option("", "--output", "-o", help="Output file path (auto-generated if omitted)"),
) -> None:
    """Export the problem statement to HTML or LaTeX."""
    init_db()
    conn = get_connection()
    try:
        problem = Problem.find_by_slug(conn, slug)
        if problem is None:
            console.print(f"[red]Problem '{slug}' not found[/red]")
            raise typer.Exit(1)
    finally:
        conn.close()

    st_path = layout.statement_path(slug)
    if not st_path.exists():
        console.print("[yellow]No statement file found. Run 'lp statement edit' first.[/yellow]")
        raise typer.Exit(1)

    md_text = st_path.read_text(encoding="utf-8")
    title = problem.title

    if fmt == "html":
        result = render_html_page(md_text, title)
        ext = ".html"
    elif fmt in ("tex", "latex"):
        result = render_latex_page(md_text, title)
        ext = ".tex"
    else:
        console.print(f"[red]Unknown format '{fmt}'. Use 'html' or 'tex'.[/red]")
        raise typer.Exit(1)

    if output:
        out_path = Path(output)
    else:
        out_path = layout.problem_dir(slug) / f"statement{ext}"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    console.print(f"[green]Exported to {out_path}[/green]")
