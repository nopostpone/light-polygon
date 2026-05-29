from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from light_polygon.db.models import TestCase
from light_polygon.judge.compiler import compile_source
from light_polygon.judge.sandbox import run_sandboxed
from light_polygon.problem import layout
from light_polygon.tests.generator import (
    _make_seed,
    compile_validator,
    generate_answer,
    get_testlib_include_dir,
    run_generator,
    validate_input,
)
from light_polygon.tests.toml_config import (
    TestsToml,
    ManualTest,
    GeneratorConfig,
    GeneratorInvocation,
    generate_template_toml,
    read_tests_toml,
    write_tests_toml,
)

HAS_GPP = os.environ.get("CI") or subprocess.call(
    ["g++", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
) == 0


class TestTomlConfig:
    def test_read_no_file_returns_empty(self, temp_data_dir):
        cfg = read_tests_toml("nonexistent")
        assert cfg.slug == "nonexistent"
        assert cfg.tests == []
        assert cfg.generators == []

    def test_read_write_roundtrip(self, temp_data_dir):
        os.makedirs(layout.problem_dir("roundtrip"), exist_ok=True)
        original = TestsToml(
            slug="roundtrip",
            tests=[
                ManualTest(index=1, description="hello", is_sample=True,
                           input="1 2", answer="3"),
            ],
            generators=[
                GeneratorConfig(
                    name="gen_a", source="gen_a.cpp", testset="tests",
                    invocations=[
                        GeneratorInvocation(args=["10"], answer_by="main.cpp", count=5),
                    ],
                ),
            ],
        )
        write_tests_toml("roundtrip", original)
        parsed = read_tests_toml("roundtrip")
        assert len(parsed.tests) == 1
        assert parsed.tests[0].index == 1
        assert parsed.tests[0].input == "1 2"
        assert parsed.tests[0].answer == "3"
        assert parsed.tests[0].is_sample is True
        assert len(parsed.generators) == 1
        assert parsed.generators[0].name == "gen_a"
        assert parsed.generators[0].source == "gen_a.cpp"
        assert parsed.generators[0].invocations[0].args == ["10"]
        assert parsed.generators[0].invocations[0].answer_by == "main.cpp"
        assert parsed.generators[0].invocations[0].count == 5

    def test_read_toml_defaults_missing_fields(self, temp_data_dir):
        os.makedirs(layout.problem_dir("minimal"), exist_ok=True)
        toml_path = layout.tests_toml_path("minimal")
        toml_path.write_text("""
[[tests]]
index = 1

[generators.gen_x]
source = "gen_x.cpp"
""", encoding="utf-8")
        cfg = read_tests_toml("minimal")
        assert cfg.tests[0].description == ""
        assert cfg.tests[0].is_sample is False
        assert cfg.tests[0].input == ""
        assert cfg.generators[0].testset == "tests"
        assert cfg.generators[0].invocations == []

    def test_template_contains_markers(self):
        tmpl = generate_template_toml("test-problem")
        assert "test-problem" in tmpl
        assert "[[tests]]" in tmpl
        assert "[generators." in tmpl
        assert "testlib.h" in tmpl
        assert "registerGen" in tmpl


class TestSeedGeneration:
    def test_seed_is_deterministic(self):
        s1 = _make_seed("gen_small", 0, 0)
        s2 = _make_seed("gen_small", 0, 0)
        assert s1 == s2

    def test_seed_differs_by_generator_name(self):
        s1 = _make_seed("gen_a", 0, 0)
        s2 = _make_seed("gen_b", 0, 0)
        assert s1 != s2

    def test_seed_increases_with_count(self):
        s0 = _make_seed("gen_x", 0, 0)
        s1 = _make_seed("gen_x", 0, 1)
        s2 = _make_seed("gen_x", 0, 2)
        assert s0 + 1 == s1
        assert s1 + 1 == s2

    def test_seed_in_range(self):
        for i in range(100):
            s = _make_seed("test", i, 0)
            assert 100000 <= s <= 99999999


class TestCaseSaveBugfix:
    def test_save_persists_generator_field(self, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="savefix-1", title="Save Fix 1", owner_id=logged_in_user.id,
        )
        tc = TestCase.create(
            db, problem_id=problem.id, test_index=1, testset="tests",
            description="test", is_sample=False, generator="gen_x:12345",
        )
        try:
            assert tc.generator == "gen_x:12345"
            tc.generator = "gen_y:99999"
            tc.save(db)
            reloaded = TestCase.find_by_id(db, tc.id)
            assert reloaded.generator == "gen_y:99999"
        finally:
            tc.delete(db)

    def test_save_persists_testset_field(self, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="savefix-2", title="Save Fix 2", owner_id=logged_in_user.id,
        )
        tc = TestCase.create(
            db, problem_id=problem.id, test_index=2, testset="pretests",
        )
        try:
            assert tc.testset == "pretests"
            tc.testset = "samples"
            tc.save(db)
            reloaded = TestCase.find_by_id(db, tc.id)
            assert reloaded.testset == "samples"
        finally:
            tc.delete(db)


class TestCompilerIncludeDirs:
    def test_include_dirs_adds_I_flags(self, tmp_path):
        # Create a real file so compile_source() can compute its hash
        src = tmp_path / "test.cpp"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            compile_source(
                src, "cpp",
                include_dirs=["/path/to/headers", "/another/include"],
            )
            cmd = mock_run.call_args[0][0]
            # Check -I flags are after compiler name and before -std
            assert "-I/path/to/headers" in cmd
            assert "-I/another/include" in cmd
            i_s = cmd.index("-I/path/to/headers")
            std_i = cmd.index("-std=c++17")
            assert i_s < std_i


class TestTestlibInclusion:
    def test_testlib_header_exists(self):
        path = get_testlib_include_dir() / "testlib.h"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "registerGen" in content
        assert "rnd.next" in content


class TestGenerateAnswer:
    def test_empty_answer_by_returns_empty(self, temp_data_dir):
        result, error = generate_answer(None, "", "input data")  # type: ignore
        assert result == ""
        assert error is None


@pytest.mark.skipif(not HAS_GPP, reason="g++ not available")
class TestGeneratorCompile:
    def test_minimal_generator_compiles(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="gen-test", title="Gen Test", owner_id=logged_in_user.id,
        )

        gen_dir = layout.generators_dir("gen-test")
        gen_dir.mkdir(parents=True, exist_ok=True)
        gen_src = gen_dir / "minimal.cpp"
        gen_src.write_text("""#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    int n = opt<int>(1);
    std::cout << n << " " << rnd.next(1, n) << std::endl;
    return 0;
}
""", encoding="utf-8")

        from light_polygon.tests.generator import compile_generator
        gen_config = GeneratorConfig(name="minimal", source="minimal.cpp")
        result = compile_generator("gen-test", gen_config)
        assert result.success, f"Compile failed: {result.errors}"
        assert result.executable_path.exists()

    def test_generator_runs_and_produces_output(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="gen-run", title="Gen Run", owner_id=logged_in_user.id,
        )
        gen_dir = layout.generators_dir("gen-run")
        gen_dir.mkdir(parents=True, exist_ok=True)
        gen_src = gen_dir / "simple.cpp"
        gen_src.write_text("""#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    std::cout << opt<int>(1) << " " << opt<int>(2) << std::endl;
    return 0;
}
""", encoding="utf-8")

        from light_polygon.tests.generator import compile_generator
        gen_config = GeneratorConfig(name="simple", source="simple.cpp")
        compile_result = compile_generator("gen-run", gen_config)
        assert compile_result.success, f"Compile failed: {compile_result.errors}"

        result = run_generator(
            compile_result.executable_path, ["42", "99"], 12345,
            layout.problem_dir("gen-run"),
        )
        # testlib.h on Windows+MSYS2 g++ may exit non-zero (0xC0000005)
        # after producing correct output; accept non-empty stdout
        assert result.stdout.strip(), f"Generator produced no output: stderr={result.stderr}"
        assert "42 99" in result.stdout


@pytest.mark.skipif(not HAS_GPP, reason="g++ not available")
class TestEndToEndGeneration:
    def test_full_generation_flow(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        from light_polygon.tests.generator import execute_generators

        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="e2e-gen", title="E2E Gen", owner_id=logged_in_user.id,
        )

        # Write generator source
        gen_dir = layout.generators_dir("e2e-gen")
        gen_src = gen_dir / "gen_test.cpp"
        gen_src.write_text("""#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    std::cout << opt<int>(1) << " " << opt<int>(2) << std::endl;
    return 0;
}
""", encoding="utf-8")

        # Write tests.toml
        tests_toml = TestsToml(
            slug="e2e-gen",
            tests=[
                ManualTest(index=1, description="手动样例", is_sample=True,
                           input="1 2", answer="3"),
            ],
            generators=[
                GeneratorConfig(
                    name="gen_test", source="gen_test.cpp",
                    invocations=[
                        GeneratorInvocation(args=["7", "13"], count=2),
                    ],
                ),
            ],
        )
        write_tests_toml("e2e-gen", tests_toml)

        count = execute_generators(problem, tests_toml)
        assert count == 3  # 1 manual + 2 generated

        # Verify manual test on disk
        manual_input = layout.test_input_path("e2e-gen", 1).read_text(encoding="utf-8")
        assert manual_input == "1 2"
        manual_answer = layout.test_answer_path("e2e-gen", 1).read_text(encoding="utf-8")
        assert manual_answer == "3"

        # Verify generated tests on disk
        gen_input = layout.test_input_path("e2e-gen", 2).read_text(encoding="utf-8")
        assert "7 13" in gen_input

        # Verify DB records
        tests = TestCase.find_by_problem(db, problem.id)
        assert len(tests) == 3
        assert tests[0].is_sample is True
        assert tests[0].generator == "manual"
        assert tests[1].generator.startswith("gen_test[0]:")
        assert tests[2].generator.startswith("gen_test[0]:")
        # Seeds should differ
        assert tests[1].generator != tests[2].generator

    def test_generator_crash_is_skipped(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        from light_polygon.tests.generator import execute_generators

        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="crash-gen", title="Crash Gen", owner_id=logged_in_user.id,
        )

        gen_dir = layout.generators_dir("crash-gen")
        gen_src = gen_dir / "crash.cpp"
        gen_src.write_text("""#include "testlib.h"
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    exit(1);
    return 0;
}
""", encoding="utf-8")

        tests_toml = TestsToml(
            slug="crash-gen",
            tests=[ManualTest(index=1, description="ok", input="1", answer="1")],
            generators=[
                GeneratorConfig(
                    name="crash", source="crash.cpp",
                    invocations=[GeneratorInvocation(args=[])],
                ),
            ],
        )
        write_tests_toml("crash-gen", tests_toml)

        count = execute_generators(problem, tests_toml)
        # Only the manual test should be created, generator is skipped
        assert count == 1
        tests = TestCase.find_by_problem(db, problem.id)
        assert len(tests) == 1
        assert tests[0].generator == "manual"

    def test_generator_count_creates_multiple(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        from light_polygon.tests.generator import execute_generators

        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="multi-gen", title="Multi Gen", owner_id=logged_in_user.id,
        )

        gen_dir = layout.generators_dir("multi-gen")
        gen_src = gen_dir / "multi.cpp"
        gen_src.write_text("""#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    std::cout << rnd.next(1, 1000000) << std::endl;
    return 0;
}
""", encoding="utf-8")

        tests_toml = TestsToml(
            slug="multi-gen",
            generators=[
                GeneratorConfig(
                    name="multi", source="multi.cpp",
                    invocations=[GeneratorInvocation(args=[], count=5)],
                ),
            ],
        )
        write_tests_toml("multi-gen", tests_toml)
        count = execute_generators(problem, tests_toml)
        assert count == 5

        # All 5 inputs should be different (different seeds)
        inputs = []
        for i in range(1, 6):
            data = layout.test_input_path("multi-gen", i).read_text(encoding="utf-8")
            inputs.append(data.strip())
        assert len(set(inputs)) == 5, f"Expected 5 unique inputs, got duplicates: {inputs}"


@pytest.mark.skipif(not HAS_GPP, reason="g++ not available")
class TestValidator:
    def test_validator_compiles(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        mgr.create(slug="val-compile", title="Val Compile", owner_id=logged_in_user.id)

        val_path = layout.files_dir("val-compile") / "validator.cpp"
        val_path.parent.mkdir(parents=True, exist_ok=True)
        val_path.write_text("""#include "testlib.h"
int main(int argc, char* argv[]) {
    registerValidation(argc, argv);
    int n = inf.readInt(1, 100, "n");
    inf.readEoln();
    inf.readEof();
    return 0;
}
""", encoding="utf-8")

        result = compile_validator("val-compile")
        assert result is not None
        assert result.success, f"Compile failed: {result.errors}"
        assert result.executable_path.exists()

    def test_validator_passes_good_input(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        mgr.create(slug="val-pass", title="Val Pass", owner_id=logged_in_user.id)

        val_path = layout.files_dir("val-pass") / "validator.cpp"
        val_path.parent.mkdir(parents=True, exist_ok=True)
        val_path.write_text("""#include "testlib.h"
int main(int argc, char* argv[]) {
    registerValidation(argc, argv);
    int n = inf.readInt(1, 100, "n");
    inf.readEoln();
    auto a = inf.readInts(n, 1, 1000000, "a_i");
    inf.readEoln();
    inf.readEof();
    return 0;
}
""", encoding="utf-8")

        result = compile_validator("val-pass")
        assert result is not None and result.success
        ok, msg = validate_input(result.executable_path, "3\n1 2 3\n")
        assert ok, f"Validation should pass: {msg}"

    def test_validator_rejects_bad_input(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        mgr = ProblemManager(db)
        mgr.create(slug="val-reject", title="Val Reject", owner_id=logged_in_user.id)

        val_path = layout.files_dir("val-reject") / "validator.cpp"
        val_path.parent.mkdir(parents=True, exist_ok=True)
        val_path.write_text("""#include "testlib.h"
int main(int argc, char* argv[]) {
    registerValidation(argc, argv);
    int n = inf.readInt(1, 10, "n");
    inf.readEoln();
    ensuref(n <= 5, "n must be at most 5, got %d", n);
    inf.readEof();
    return 0;
}
""", encoding="utf-8")

        result = compile_validator("val-reject")
        assert result is not None and result.success
        ok, msg = validate_input(result.executable_path, "8\n")
        assert not ok, "Validation should reject n=8 when max is 5"
        assert "5" in msg or "must" in msg.lower()

    def test_generate_skips_invalid_test(self, temp_data_dir, db, logged_in_user):
        from light_polygon.problem.manager import ProblemManager
        from light_polygon.tests.generator import execute_generators

        mgr = ProblemManager(db)
        problem = mgr.create(
            slug="val-skip", title="Val Skip", owner_id=logged_in_user.id,
        )

        # Validator: n must be between 1 and 10
        val_path = layout.files_dir("val-skip") / "validator.cpp"
        val_path.parent.mkdir(parents=True, exist_ok=True)
        val_path.write_text("""#include "testlib.h"
int main(int argc, char* argv[]) {
    registerValidation(argc, argv);
    int n = inf.readInt(1, 10, "n");
    inf.readEoln();
    ensuref(n <= 10, "n too large");
    inf.readEof();
    return 0;
}
""", encoding="utf-8")

        # Generator: outputs "20\n" (invalid — exceeds max n=10)
        gen_dir = layout.generators_dir("val-skip")
        gen_src = gen_dir / "big.cpp"
        gen_src.write_text("""#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    std::cout << 20 << std::endl;
    return 0;
}
""", encoding="utf-8")

        tests_toml = TestsToml(
            slug="val-skip",
            tests=[ManualTest(index=1, description="valid", input="5\n", answer="")],
            generators=[
                GeneratorConfig(
                    name="big", source="big.cpp",
                    invocations=[GeneratorInvocation(args=[], count=2)],
                ),
            ],
        )
        write_tests_toml("val-skip", tests_toml)
        count = execute_generators(problem, tests_toml)

        # Only the valid manual test should be created; generator tests skipped
        assert count == 1
        tests = TestCase.find_by_problem(db, problem.id)
        assert len(tests) == 1
        assert tests[0].generator == "manual"
        assert tests[0].test_index == 1
