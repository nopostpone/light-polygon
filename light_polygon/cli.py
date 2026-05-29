from __future__ import annotations

import typer

from light_polygon.auth.commands import auth_app
from light_polygon.export.commands import export_app
from light_polygon.judge.commands import judge_app
from light_polygon.problem.commands import problem_app
from light_polygon.solution.commands import solution_app
from light_polygon.statement.commands import statement_app
from light_polygon.tests.commands import test_app
from light_polygon.utils.console import console

app = typer.Typer(
    name="light-polygon",
    help="Lightweight Codeforces-style Polygon for algorithm competition problem preparation.",
    no_args_is_help=True,
)


@app.callback()
def main(
    data_dir: str = typer.Option(
        "",
        "--data-dir",
        help="Override the data directory path.",
    ),
) -> None:
    if data_dir:
        from light_polygon.config import get_config

        cfg = get_config()
        cfg.data_dir = data_dir


app.add_typer(auth_app, name="user", help="User management")
app.add_typer(problem_app, name="problem", help="Problem management")
app.add_typer(test_app, name="test", help="Test case management")
app.add_typer(solution_app, name="solution", help="Solution management")
app.add_typer(statement_app, name="statement", help="Statement management")
app.add_typer(export_app, name="export", help="Export problem data")
app.add_typer(judge_app, name="judge", help="Judging and evaluation")


def main_entry() -> None:
    app()
