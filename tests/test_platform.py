from __future__ import annotations


from light_polygon.platform import (
    get_compiler_executable,
    get_system,
    is_linux,
    is_macos,
    is_windows,
    normalize_executable_path,
    normalize_exit_code,
)


class TestSystemDetection:
    def test_get_system_returns_string(self):
        s = get_system()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_platform_mutually_exclusive(self):
        """Exactly one platform should be true."""
        flags = [is_windows(), is_macos(), is_linux()]
        assert sum(flags) == 1, f"Expected exactly one platform, got: {flags}"


class TestCompilerExecutable:
    def test_cpp_returns_gpp(self):
        assert get_compiler_executable("cpp") == "g++"
        assert get_compiler_executable("c++") == "g++"

    def test_c_returns_gcc(self):
        assert get_compiler_executable("c") == "gcc"

    def test_unknown_returns_gpp(self):
        assert get_compiler_executable("rust") == "g++"


class TestNormalizeExecutablePath:
    def test_existing_file_unchanged(self, tmp_path):
        f = tmp_path / "prog"
        f.write_text("binary")
        result = normalize_executable_path(f)
        assert result == f

    def test_exe_fallback_when_base_missing(self, tmp_path):
        """On Windows, g++ creates prog.exe. normalize should find it."""
        exe = tmp_path / "prog.exe"
        exe.write_text("binary")
        base = tmp_path / "prog"
        result = normalize_executable_path(base)
        assert result == exe

    def test_missing_both_returns_original(self, tmp_path):
        base = tmp_path / "nothing"
        result = normalize_executable_path(base)
        assert result == base


class TestNormalizeExitCode:
    def test_normal_code_unchanged(self):
        assert normalize_exit_code(0) == 0
        assert normalize_exit_code(1) == 1
        assert normalize_exit_code(42) == 42

    def test_msys2_crash_with_empty_stderr_on_windows(self):
        """0xC0000005 with empty stderr should normalize to 0 on Windows."""
        if is_windows():
            assert normalize_exit_code(-1073741819, stderr="") == 0
        else:
            # On non-Windows, the code should pass through
            # (the crash code is Windows-specific anyway)
            pass

    def test_msys2_crash_with_stderr_not_normalized(self):
        """0xC0000005 with actual stderr output should NOT be normalized."""
        if is_windows():
            assert (
                normalize_exit_code(-1073741819, stderr="error output") == -1073741819
            )
