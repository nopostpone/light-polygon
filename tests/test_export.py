from __future__ import annotations

import json
import zipfile

from typer.testing import CliRunner

from light_polygon.cli import app


runner = CliRunner()


def _login(runner: CliRunner) -> None:
    result = runner.invoke(app, ["user", "register", "author"], input="pass\npass\n")
    assert result.exit_code == 0
    result = runner.invoke(app, ["user", "login", "author"], input="pass\n")
    assert result.exit_code == 0


def _create_problem(runner: CliRunner, slug: str, title: str = "Test") -> None:
    result = runner.invoke(
        app,
        [
            "problem",
            "create",
            slug,
            "--title",
            title,
            "--tl",
            "2000",
            "--ml",
            "512",
        ],
    )
    assert result.exit_code == 0, f"Create failed: {result.output}"


def _add_solution(
    runner: CliRunner, slug: str, code: str, name: str, tag: str = "AC"
) -> None:
    from light_polygon.problem import layout

    sol_dir = layout.solutions_dir(slug)
    sol_dir.mkdir(parents=True, exist_ok=True)
    sol_path = sol_dir / name
    sol_path.write_text(code, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "solution",
            "add",
            slug,
            str(sol_path),
            "--tag",
            tag,
            "--as",
            name,
        ],
    )
    assert result.exit_code == 0, f"Solution add failed: {result.output}"


def _add_test(
    runner: CliRunner, slug: str, idx: int, inp: str, ans: str, is_sample: bool = False
) -> None:
    from light_polygon.problem import layout

    td = layout.tests_dir(slug)
    td.mkdir(parents=True, exist_ok=True)
    in_path = td / f"{idx:02d}"
    ans_path = td / f"{idx:02d}.a"
    in_path.write_text(inp, encoding="utf-8")
    ans_path.write_text(ans, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "test",
            "add",
            slug,
            "--input",
            str(in_path),
            "--answer",
            str(ans_path),
        ]
        + (["--sample"] if is_sample else []),
    )
    assert result.exit_code == 0, f"Test add failed: {result.output}"


class TestExportNative:
    def test_export_empty_problem(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "empty-prob")

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "empty-prob",
                "--output",
                str(temp_data_dir),
                "--format",
                "native",
            ],
        )
        assert result.exit_code == 0, result.output

        zip_path = temp_data_dir / "empty-prob-native.zip"
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "empty-prob/problem.toml" in names
            assert "empty-prob/statement.md" in names

    def test_export_native_complete(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "full-prob")
        _add_solution(runner, "full-prob", "print(1+2)", "solve.py", "AC")
        _add_solution(runner, "full-prob", "print(0)", "wrong.py", "WA")
        _add_test(runner, "full-prob", 1, "1 2", "3")
        _add_test(runner, "full-prob", 2, "5 7", "12")

        # Add a generator source
        from light_polygon.problem import layout

        gen_dir = layout.generators_dir("full-prob")
        gen_dir.mkdir(parents=True, exist_ok=True)
        (gen_dir / "gen.cpp").write_text("// generator", encoding="utf-8")

        # Add a validator
        files_dir = layout.files_dir("full-prob")
        (files_dir / "validator.cpp").write_text("// validator", encoding="utf-8")

        # Add tests.toml
        (layout.problem_dir("full-prob") / "tests.toml").write_text(
            "# config", encoding="utf-8"
        )

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "full-prob",
                "--output",
                str(temp_data_dir),
                "--format",
                "native",
            ],
        )
        assert result.exit_code == 0, result.output

        zip_path = temp_data_dir / "full-prob-native.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "full-prob/problem.toml" in names
            assert "full-prob/statement.md" in names
            assert "full-prob/tests/01" in names
            assert "full-prob/tests/01.a" in names
            assert "full-prob/tests/02" in names
            assert "full-prob/tests/02.a" in names
            assert "full-prob/solutions/solve.py" in names
            assert "full-prob/solutions/wrong.py" in names  # native includes all
            assert "full-prob/generators/gen.cpp" in names
            assert "full-prob/files/validator.cpp" in names
            assert "full-prob/tests.toml" in names


class TestExportPolygon:
    def test_export_polygon_format(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "poly-prob")
        _add_solution(runner, "poly-prob", "print(1+2)", "solve.py", "AC")
        _add_solution(runner, "poly-prob", "print(0)", "wrong.py", "WA")
        _add_test(runner, "poly-prob", 1, "1 2", "3")
        _add_test(runner, "poly-prob", 2, "5 7", "12")

        from light_polygon.problem import layout

        files_dir = layout.files_dir("poly-prob")
        (files_dir / "validator.cpp").write_text("// validator", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "poly-prob",
                "--output",
                str(temp_data_dir),
                "--format",
                "polygon",
            ],
        )
        assert result.exit_code == 0, result.output

        zip_path = temp_data_dir / "poly-prob-polygon.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            # problem.json instead of problem.toml
            assert "poly-prob/problem.json" in names
            assert "poly-prob/problem.toml" not in names
            # No generators or tests.toml
            assert "poly-prob/tests.toml" not in names
            # Statement, tests, solutions (AC only), files included
            assert "poly-prob/statement.md" in names
            assert "poly-prob/tests/01" in names
            assert "poly-prob/tests/01.a" in names
            assert "poly-prob/files/validator.cpp" in names
            assert "poly-prob/solutions/solve.py" in names
            # WA solution filtered out by default
            assert "poly-prob/solutions/wrong.py" not in names

    def test_export_polygon_problem_json_schema(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "schema-prob", title="Schema Test")
        _add_test(runner, "schema-prob", 1, "1", "2")
        _add_test(runner, "schema-prob", 2, "3", "4")

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "schema-prob",
                "--output",
                str(temp_data_dir),
                "--format",
                "polygon",
            ],
        )
        assert result.exit_code == 0

        zip_path = temp_data_dir / "schema-prob-polygon.zip"
        with zipfile.ZipFile(zip_path) as zf:
            data = json.loads(zf.read("schema-prob/problem.json"))
            assert data["schema_version"] == "1.0"
            assert data["name"] == "schema-prob"
            assert data["title"] == "Schema Test"
            assert data["time_limit"] == 2000
            assert data["memory_limit"] == 512
            assert data["input_file"] == "stdin"
            assert data["output_file"] == "stdout"
            assert data["statement"]["format"] == "markdown"
            assert data["test_count"] == 2
            assert data["test_format"]["input_pattern"] == "{index:02d}"
            assert data["test_format"]["answer_pattern"] == "{index:02d}.a"

    def test_export_all_solutions_flag(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "all-sol")
        _add_solution(runner, "all-sol", "print(1)", "ac.py", "AC")
        _add_solution(runner, "all-sol", "print(0)", "wa.py", "WA")

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "all-sol",
                "--output",
                str(temp_data_dir),
                "--format",
                "polygon",
                "--all-solutions",
            ],
        )
        assert result.exit_code == 0

        zip_path = temp_data_dir / "all-sol-polygon.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "all-sol/solutions/ac.py" in names
            assert "all-sol/solutions/wa.py" in names


class TestExportErrors:
    def test_export_missing_problem_errors(self, temp_data_dir):
        _login(runner)
        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "nonexistent",
                "--output",
                str(temp_data_dir),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_export_unknown_format_errors(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "fmt-err")
        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "fmt-err",
                "--output",
                str(temp_data_dir),
                "--format",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "unknown format" in result.output.lower()


class TestExportOutput:
    def test_export_custom_output_path(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "cust-out")
        custom = temp_data_dir / "my-problem.zip"

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "cust-out",
                "--output",
                str(custom),
                "--format",
                "native",
            ],
        )
        assert result.exit_code == 0, result.output
        assert custom.exists()

    def test_export_default_output_name(self, temp_data_dir):
        import os

        _login(runner)
        _create_problem(runner, "def-out")

        cwd = os.getcwd()
        try:
            os.chdir(str(temp_data_dir))
            result = runner.invoke(
                app,
                [
                    "export",
                    "package",
                    "def-out",
                    "--format",
                    "native",
                ],
            )
            assert result.exit_code == 0, result.output
            expected = temp_data_dir / "def-out-native.zip"
            assert expected.exists(), (
                f"Expected {expected}, got: {list(temp_data_dir.iterdir())}"
            )
        finally:
            os.chdir(cwd)


class TestExportEdgeCases:
    def test_export_handles_missing_statement(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "no-stmt")

        # Delete statement.md
        from light_polygon.problem import layout

        st = layout.statement_path("no-stmt")
        st.unlink()
        assert not st.exists()

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "no-stmt",
                "--output",
                str(temp_data_dir),
                "--format",
                "native",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Warning" in result.output

        zip_path = temp_data_dir / "no-stmt-native.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "no-stmt/statement.md" not in names
            assert "no-stmt/problem.toml" in names

    def test_export_empty_files_dir_not_included(self, temp_data_dir):
        _login(runner)
        _create_problem(runner, "no-files")

        result = runner.invoke(
            app,
            [
                "export",
                "package",
                "no-files",
                "--output",
                str(temp_data_dir),
                "--format",
                "polygon",
            ],
        )
        assert result.exit_code == 0

        zip_path = temp_data_dir / "no-files-polygon.zip"
        with zipfile.ZipFile(zip_path) as zf:
            dir_entries = [n for n in zf.namelist() if n.startswith("no-files/files/")]
            assert len(dir_entries) == 0, (
                f"Empty files/ should not appear: {dir_entries}"
            )
