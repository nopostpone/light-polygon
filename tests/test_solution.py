from __future__ import annotations

from pathlib import Path


from light_polygon.db.models import Solution
from light_polygon.solution.manager import add_solution_file, language_from_path


class TestLanguageFromPath:
    def test_cpp_extensions(self):
        assert language_from_path("solve.cpp") == "cpp"
        assert language_from_path("solve.cc") == "cpp"
        assert language_from_path("solve.cxx") == "cpp"

    def test_c_extension(self):
        assert language_from_path("solve.c") == "c"

    def test_python_extension(self):
        assert language_from_path("solve.py") == "python"

    def test_java_extension(self):
        assert language_from_path("Main.java") == "java"

    def test_go_extension(self):
        assert language_from_path("solve.go") == "go"

    def test_rust_extension(self):
        assert language_from_path("solve.rs") == "rust"

    def test_js_extension(self):
        assert language_from_path("solve.js") == "javascript"

    def test_ts_extension(self):
        assert language_from_path("solve.ts") == "typescript"

    def test_kt_extension(self):
        assert language_from_path("solve.kt") == "kotlin"

    def test_unknown_extension(self):
        assert language_from_path("solve.xyz") == "unknown"
        assert language_from_path("Makefile") == "unknown"

    def test_path_object(self):
        assert language_from_path(Path("solve.cpp")) == "cpp"

    def test_case_insensitive(self):
        assert language_from_path("solve.PY") == "python"
        assert language_from_path("solve.CPP") == "cpp"


class TestAddSolutionFile:
    def test_copies_file_to_solutions_dir(self, temp_data_dir):
        # Create a source file
        src = Path(temp_data_dir) / "original_sol.py"
        src.write_text("print('hello')")

        dest = add_solution_file("test-problem", "sol.py", src)

        assert dest.exists()
        assert dest.name == "sol.py"
        assert "solutions" in str(dest)
        assert dest.read_text() == "print('hello')"

    def test_creates_directories_if_missing(self, temp_data_dir):
        src = Path(temp_data_dir) / "new_sol.cpp"
        src.write_text("int main() { return 0; }")

        dest = add_solution_file("fresh-problem", "main.cpp", src)

        assert dest.exists()
        assert dest.parent.is_dir()


class TestSolutionModel:
    def test_create_and_find(self, sample_problem, db):
        sol = Solution.create(
            db,
            problem_id=sample_problem.id,
            name="ac_sol.py",
            language="python",
            source_path="solutions/ac_sol.py",
            tag="AC",
        )
        assert sol.id is not None

        found = Solution.find_by_id(db, sol.id)
        assert found is not None
        assert found.name == "ac_sol.py"
        assert found.tag == "AC"

    def test_find_by_problem(self, sample_problem, db):
        Solution.create(
            db,
            problem_id=sample_problem.id,
            name="sol1.py",
            language="python",
            source_path="solutions/sol1.py",
        )
        Solution.create(
            db,
            problem_id=sample_problem.id,
            name="sol2.py",
            language="python",
            source_path="solutions/sol2.py",
        )

        sols = Solution.find_by_problem(db, sample_problem.id)
        assert len(sols) == 2
        names = {s.name for s in sols}
        assert "sol1.py" in names
        assert "sol2.py" in names

    def test_save_updates_fields(self, sample_problem, db):
        sol = Solution.create(
            db,
            problem_id=sample_problem.id,
            name="update_me.py",
            language="python",
            source_path="solutions/update_me.py",
            tag="WA",
            description="old desc",
        )

        sol.tag = "AC"
        sol.description = "now it works"
        sol.save(db)

        reloaded = Solution.find_by_id(db, sol.id)
        assert reloaded.tag == "AC"
        assert reloaded.description == "now it works"

    def test_delete_removes_solution(self, sample_problem, db):
        sol = Solution.create(
            db,
            problem_id=sample_problem.id,
            name="delete_me.py",
            language="python",
            source_path="solutions/delete_me.py",
        )

        sol.delete(db)

        found = Solution.find_by_id(db, sol.id)
        assert found is None

    def test_find_nonexistent_returns_none(self, db):
        assert Solution.find_by_id(db, 99999) is None

    def test_find_by_problem_empty(self, sample_problem, db):
        sols = Solution.find_by_problem(db, sample_problem.id)
        assert sols == []
