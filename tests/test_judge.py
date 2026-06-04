from __future__ import annotations


from light_polygon.db.models import Solution
from light_polygon.judge.compiler import compile_source
from light_polygon.judge.service import judge_all
from light_polygon.problem import layout


def test_compile_python_nop(tmp_path):
    src = tmp_path / "hello.py"
    src.write_text("print('hello')")
    result = compile_source(src, "python")
    assert result.success
    assert result.executable_path == src


def test_judge_python_solution(sample_problem, db):
    """End-to-end test: Python solution, wcmp checker."""
    from light_polygon.tests.manager import TestManager

    slug = sample_problem.slug

    # Add a test case
    tm = TestManager(db, slug)
    tm.add(sample_problem.id, test_index=1, input_data="3 5\n", answer_data="8\n")

    # Add a Python solution
    sol_path = layout.solutions_dir(slug) / "solve.py"
    sol_path.parent.mkdir(parents=True, exist_ok=True)
    sol_path.write_text(
        "import sys\na, b = map(int, sys.stdin.read().split())\nprint(a + b)\n"
    )

    Solution.create(
        db,
        problem_id=sample_problem.id,
        name="solve.py",
        language="python",
        source_path="solutions/solve.py",
        tag="AC",
    )

    # Judge using new service API
    summary = judge_all(db, sample_problem, checker_name="wcmp")
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
    sol_path.write_text(
        "import sys\na, b = map(int, sys.stdin.read().split())\nprint(a * b)\n"
    )

    Solution.create(
        db,
        problem_id=sample_problem.id,
        name="wrong.py",
        language="python",
        source_path="solutions/wrong.py",
        tag="WA",
    )

    summary = judge_all(db, sample_problem, checker_name="wcmp")
    assert len(summary.results) == 1
    assert summary.results[0].verdict == "WA"
