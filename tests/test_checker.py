from __future__ import annotations

from unittest import mock


from light_polygon.judge.checker import (
    STANDARD_CHECKERS,
    get_checker_source_path,
    get_standard_checker_path,
    parse_testlib_exit_code,
    run_testlib_checker,
)
from light_polygon.judge.sandbox import SandboxResult


class TestParseTestlibExitCode:
    def test_ok_returns_ac(self):
        assert parse_testlib_exit_code(0) == "AC"

    def test_wa_returns_wa(self):
        assert parse_testlib_exit_code(1) == "WA"

    def test_pe_returns_pe(self):
        assert parse_testlib_exit_code(2) == "PE"

    def test_fail_returns_fail(self):
        assert parse_testlib_exit_code(3) == "FAIL"

    def test_points_returns_ac(self):
        assert parse_testlib_exit_code(7) == "AC"

    def test_unknown_code_returns_wa(self):
        assert parse_testlib_exit_code(99) == "WA"
        assert parse_testlib_exit_code(-1) == "WA"


class TestStandardCheckers:
    def test_all_standard_checkers_listed(self):
        assert len(STANDARD_CHECKERS) == 10
        assert "wcmp" in STANDARD_CHECKERS
        assert "ncmp" in STANDARD_CHECKERS

    def test_valid_checker_returns_path(self):
        path = get_standard_checker_path("wcmp")
        assert path is not None
        assert path.name == "wcmp.cpp"
        assert path.exists()

    def test_each_standard_checker_exists(self):
        for name in STANDARD_CHECKERS:
            path = get_standard_checker_path(name)
            assert path is not None, f"Standard checker '{name}' has no path"
            assert path.exists(), f"Standard checker source missing: {path}"

    def test_unknown_checker_returns_none(self):
        assert get_standard_checker_path("nonexistent") is None
        assert get_standard_checker_path("") is None


class TestGetCheckerSourcePath:
    def test_standard_checker_bundled(self):
        path = get_checker_source_path("any-problem", "wcmp")
        assert path is not None
        assert "vendor" in str(path)

    def test_custom_checker_looks_in_problem_dir(self, temp_data_dir):
        from light_polygon.problem import layout

        problem_dir = layout.problem_dir("custom-problem")
        checker_dir = problem_dir / "checkers"
        checker_dir.mkdir(parents=True, exist_ok=True)
        (checker_dir / "checker.cpp").write_text("// custom checker")

        path = get_checker_source_path("custom-problem", "custom")
        assert path is not None
        assert str(path).endswith("checker.cpp")

    def test_unknown_checker_name_returns_none(self):
        path = get_checker_source_path("any-problem", "unknown-checker")
        assert path is None


class TestRunTestlibChecker:
    def test_ac_on_exit_0(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=0, stdout="ok", stderr=""
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "AC"
            assert result.score == 1.0

    def test_wa_on_exit_1(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=1, stdout="", stderr="wrong answer"
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "WA"
            assert result.score == 0.0
            assert "wrong answer" in result.message

    def test_pe_on_exit_2(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=2, stdout="", stderr="bad format"
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "PE"
            assert result.score == 0.0

    def test_fail_on_exit_3(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=3, stdout="", stderr="checker crashed"
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "FAIL"

    def test_fail_with_empty_stderr_provides_message(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=3, stdout="", stderr=""
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "FAIL"
            assert "exit code 3" in result.message

    def test_wa_with_empty_stderr_provides_message(self):
        with mock.patch("light_polygon.judge.checker.run_sandboxed") as mock_run:
            mock_run.return_value = SandboxResult(
                verdict="AC", exit_code=1, stdout="", stderr=""
            )
            result = run_testlib_checker(
                mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
            )
            assert result.verdict == "WA"
            assert "exit code" in result.message
