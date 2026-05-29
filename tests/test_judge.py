from __future__ import annotations

from pathlib import Path

from light_polygon.db.models import Solution, TestCase
from light_polygon.judge.checker import check_exact, check_tokens, check_fcmp
from light_polygon.judge.compiler import compile_source
from light_polygon.judge.engine import judge_all
from light_polygon.problem import layout


def test_checker_exact_identical(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("3\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text("3\n")

    result = check_exact(input_f, out_f, ans_f)
    assert result.verdict == "AC"


def test_checker_exact_different(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("4\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text("3\n")

    result = check_exact(input_f, out_f, ans_f)
    assert result.verdict == "WA"


def test_checker_tokens_whitespace_insensitive(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("3\n4\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text(" 3  4  \n")
    result = check_tokens(input_f, out_f, ans_f)
    assert result.verdict == "AC"


def test_checker_tokens_different(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("3\n5\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text("3\n4\n")
    result = check_tokens(input_f, out_f, ans_f)
    assert result.verdict == "WA"


def test_checker_fcmp_close_enough(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("3.1415926535\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text("3.1415926536\n")
    result = check_fcmp(input_f, out_f, ans_f, epsilon=1e-6)
    assert result.verdict == "AC"


def test_checker_fcmp_too_far(tmp_path):
    input_f = tmp_path / "in.txt"
    input_f.write_text("1 2")
    out_f = tmp_path / "out.txt"
    out_f.write_text("3.14\n")
    ans_f = tmp_path / "ans.txt"
    ans_f.write_text("3.15\n")
    result = check_fcmp(input_f, out_f, ans_f, epsilon=1e-6)
    assert result.verdict == "WA"


def test_compile_python_nop(tmp_path):
    src = tmp_path / "hello.py"
    src.write_text("print('hello')")
    result = compile_source(src, "python")
    assert result.success
    assert result.executable_path == src


def test_judge_python_solution(sample_problem, db):
    """End-to-end test: Python solution, exact checker."""
    from light_polygon.tests.manager import TestManager

    slug = sample_problem.slug

    # Add a test case
    tm = TestManager(db, slug)
    tm.add(sample_problem.id, test_index=1, input_data="3 5\n", answer_data="8\n")

    # Add a Python solution
    sol_path = layout.solutions_dir(slug) / "solve.py"
    sol_path.parent.mkdir(parents=True, exist_ok=True)
    sol_path.write_text("import sys\na, b = map(int, sys.stdin.read().split())\nprint(a + b)\n")

    solution = Solution.create(
        db, problem_id=sample_problem.id, name="solve.py",
        language="python", source_path="solutions/solve.py", tag="AC",
    )

    # Judge
    summary = judge_all(sample_problem)
    assert len(summary.results) == 1
    assert summary.results[0].verdict == "AC"


def test_judge_wrong_solution(sample_problem, db):
    """Test that a wrong solution gets WA."""
    from light_polygon.tests.manager import TestManager

    slug = sample_problem.slug

    # Add a test case
    tm = TestManager(db, slug)
    tm.add(sample_problem.id, test_index=1, input_data="3 5\n", answer_data="8\n")

    # Add a wrong Python solution
    sol_path = layout.solutions_dir(slug) / "wrong.py"
    sol_path.parent.mkdir(parents=True, exist_ok=True)
    sol_path.write_text("import sys\na, b = map(int, sys.stdin.read().split())\nprint(a * b)\n")

    Solution.create(
        db, problem_id=sample_problem.id, name="wrong.py",
        language="python", source_path="solutions/wrong.py", tag="WA",
    )

    summary = judge_all(sample_problem)
    assert len(summary.results) == 1
    assert summary.results[0].verdict == "WA"
