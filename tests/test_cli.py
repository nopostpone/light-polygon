from __future__ import annotations

from typer.testing import CliRunner

from light_polygon.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "light-polygon" in result.stdout


def test_user_register_and_login(temp_data_dir):
    """Test user register, login, whoami, logout flow."""
    # Register
    result = runner.invoke(app, ["user", "register", "testuser"], input="pass1234\npass1234\n")
    assert result.exit_code == 0
    assert "registered" in result.stdout.lower()

    # Login
    result = runner.invoke(app, ["user", "login", "testuser"], input="pass1234\n")
    assert result.exit_code == 0
    assert "logged in" in result.stdout.lower()

    # Whoami
    result = runner.invoke(app, ["user", "whoami"])
    assert result.exit_code == 0
    assert "testuser" in result.stdout

    # Logout
    result = runner.invoke(app, ["user", "logout"])
    assert result.exit_code == 0


def test_problem_create_and_list(temp_data_dir):
    """Test problem creation after login."""
    # Login first
    runner.invoke(app, ["user", "register", "author"], input="pass1234\npass1234\n")
    runner.invoke(app, ["user", "login", "author"], input="pass1234\n")

    # Create
    result = runner.invoke(app, ["problem", "create", "two-sum", "--title", "Two Sum"])
    assert result.exit_code == 0
    assert "created" in result.stdout.lower()

    # List
    result = runner.invoke(app, ["problem", "list"])
    assert result.exit_code == 0
    assert "two-sum" in result.stdout

    # Info
    result = runner.invoke(app, ["problem", "info", "two-sum"])
    assert result.exit_code == 0
    assert "Two Sum" in result.stdout


def test_end_to_end_judging(temp_data_dir):
    """Full e2e: create problem, add test, add solution, judge."""
    # Setup user
    runner.invoke(app, ["user", "register", "judge_user"], input="pass1234\npass1234\n")
    runner.invoke(app, ["user", "login", "judge_user"], input="pass1234\n")

    # Create problem
    runner.invoke(app, ["problem", "create", "a-plus-b", "--title", "A+B"])

    # Add test via stdin
    result = runner.invoke(
        app, ["test", "add", "a-plus-b", "--sample", "--desc", "basic addition"],
        input="3 5\n",
    )
    assert result.exit_code == 0
    # Write answer
    from light_polygon.problem import layout
    answer_path = layout.test_answer_path("a-plus-b", 1)
    answer_path.parent.mkdir(parents=True, exist_ok=True)
    answer_path.write_text("8\n", encoding="utf-8")

    # Add a solution
    sol_dir = layout.solutions_dir("a-plus-b")
    sol_dir.mkdir(parents=True, exist_ok=True)
    sol_path = sol_dir / "solve.py"
    sol_path.write_text("import sys\na,b=map(int,sys.stdin.read().split())\nprint(a+b)\n")

    result = runner.invoke(app, ["solution", "add", "a-plus-b", str(sol_path), "--tag", "AC"])
    assert result.exit_code == 0

    # Judge
    result = runner.invoke(app, ["judge", "run", "a-plus-b"])
    assert result.exit_code == 0
    assert "AC" in result.stdout
