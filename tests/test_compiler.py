from __future__ import annotations

import subprocess
from unittest import mock

from light_polygon.judge.compiler import (
    _compute_cache_key,
    compile_source,
)


class TestCompileCacheKey:
    """Tests for content-hash based compile cache keys."""

    def test_same_source_same_key(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        k1 = _compute_cache_key(src, "cpp", None, None, None)
        k2 = _compute_cache_key(src, "cpp", None, None, None)
        assert k1 == k2

    def test_different_source_different_key(self, tmp_path):
        a = tmp_path / "a.cpp"
        b = tmp_path / "b.cpp"
        a.write_text("int main() { return 0; }")
        b.write_text("int main() { return 1; }")
        k1 = _compute_cache_key(a, "cpp", None, None, None)
        k2 = _compute_cache_key(b, "cpp", None, None, None)
        assert k1 != k2

    def test_different_flags_different_key(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        k1 = _compute_cache_key(src, "cpp", ["-O2"], None, None)
        k2 = _compute_cache_key(src, "cpp", ["-O0"], None, None)
        assert k1 != k2

    def test_different_includes_different_key(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        k1 = _compute_cache_key(src, "cpp", None, ["/a"], None)
        k2 = _compute_cache_key(src, "cpp", None, ["/b"], None)
        assert k1 != k2

    def test_different_defines_different_key(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        k1 = _compute_cache_key(src, "cpp", None, None, ["A"])
        k2 = _compute_cache_key(src, "cpp", None, None, ["B"])
        assert k1 != k2

    def test_different_language_different_key(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        k1 = _compute_cache_key(src, "cpp", None, None, None)
        k2 = _compute_cache_key(src, "c", None, None, None)
        assert k1 != k2


class TestCompileCacheHit:
    """Tests for compile cache hit/miss behaviour."""

    def test_second_compile_uses_cache(self, temp_data_dir):
        """Pre-populate cache, then call compile_source — should hit cache."""
        src = temp_data_dir / "main.cpp"
        src.write_text("int main() { return 0; }")

        # Simulate a prior compilation by pre-populating the cache
        cache_key = _compute_cache_key(src, "cpp", None, None, None)
        cache_dir = temp_data_dir / ".cache" / "compile" / cache_key
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_exe = cache_dir / "main"
        cached_exe.write_text("fake-binary")

        # Now call compile_source — should hit the cache, no subprocess call
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            result = compile_source(src, "cpp")
            assert result.success
            assert mock_run.call_count == 0, "Should hit cache, not call compiler"
            assert result.executable_path == cached_exe

    def test_no_cache_with_explicit_output_path(self, tmp_path):
        """When output_path is provided, cache is bypassed."""
        src = tmp_path / "main.cpp"
        src.write_text("int main() { return 0; }")
        out = tmp_path / "custom_out"

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            compile_source(src, "cpp", output_path=out)
            assert mock_run.call_count == 1, (
                "Should always compile when output_path is explicit"
            )

    def test_cache_key_different_with_flags(self, temp_data_dir):
        """Different flags → different cache entries."""
        src = temp_data_dir / "main.cpp"
        src.write_text("int main() { return 0; }")

        # Pre-populate cache for -O2 flag set
        key_o2 = _compute_cache_key(src, "cpp", ["-O2"], None, None)
        cache_dir_o2 = temp_data_dir / ".cache" / "compile" / key_o2
        cache_dir_o2.mkdir(parents=True, exist_ok=True)
        (cache_dir_o2 / "main").write_text("o2-binary")

        # Pre-populate cache for -O0 flag set
        key_o0 = _compute_cache_key(src, "cpp", ["-O0"], None, None)
        cache_dir_o0 = temp_data_dir / ".cache" / "compile" / key_o0
        cache_dir_o0.mkdir(parents=True, exist_ok=True)
        (cache_dir_o0 / "main").write_text("o0-binary")

        r1 = compile_source(src, "cpp", flags=["-O2"])
        r2 = compile_source(src, "cpp", flags=["-O0"])

        assert r1.success and r2.success
        assert r1.executable_path != r2.executable_path, (
            "Different flags should produce different cache entries"
        )


class TestCompilePythonNoCache:
    """Python files are returned as-is, no caching needed."""

    def test_python_file_passed_through(self, tmp_path):
        src = tmp_path / "solve.py"
        src.write_text("print(1)")
        result = compile_source(src, "python")
        assert result.success
        assert result.executable_path == src


class TestCompileMissingFile:
    def test_missing_source_returns_error(self, tmp_path):
        src = tmp_path / "nope.cpp"
        result = compile_source(src, "cpp")
        assert not result.success
        assert "not found" in result.errors.lower()


class TestCompileError:
    def test_failed_compilation_returns_errors(self, tmp_path):
        src = tmp_path / "bad.cpp"
        src.write_text("this is not valid c++")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="syntax error"
            )
            result = compile_source(src, "cpp")
            assert not result.success
            assert "syntax error" in result.errors


class TestCompileTimeout:
    def test_compilation_timeout_returns_error(self, tmp_path):
        src = tmp_path / "big.cpp"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["g++"], 30)
            result = compile_source(src, "cpp")
            assert not result.success
            assert "timed out" in result.errors.lower()


class TestCompileCompilerNotFound:
    def test_missing_compiler_returns_helpful_error(self, tmp_path):
        src = tmp_path / "a.cpp"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("g++")
            result = compile_source(src, "cpp")
            assert not result.success
            assert "not found" in result.errors.lower()
            assert "g++" in result.errors


class TestCompileCorrectFlags:
    def test_default_cpp_flags_applied(self, tmp_path):
        src = tmp_path / "main.cpp"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            compile_source(src, "cpp")
            cmd = mock_run.call_args[0][0]
            assert "-std=c++17" in cmd
            assert "-O2" in cmd
            assert "-Wall" in cmd

    def test_custom_flags_override_defaults(self, tmp_path):
        src = tmp_path / "main.cpp"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            compile_source(src, "cpp", flags=["-std=c++20"])
            cmd = mock_run.call_args[0][0]
            assert "-std=c++20" in cmd
            assert "-O2" not in cmd  # defaults not applied when custom flags given

    def test_c_language_no_default_flags(self, tmp_path):
        src = tmp_path / "main.c"
        src.write_text("int main() { return 0; }")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            compile_source(src, "c")
            cmd = mock_run.call_args[0][0]
            assert "-std=c++17" not in cmd
