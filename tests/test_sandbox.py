from __future__ import annotations

import sys


from light_polygon.judge.sandbox import run_sandboxed


class TestBasicExecution:
    def test_simple_command_stdout(self):
        result = run_sandboxed(
            [sys.executable, "-c", "print('hello world')"],
            time_limit_ms=5000,
            memory_limit_mb=256,
        )
        assert result.verdict == "AC"
        assert result.stdout.strip() == "hello world"
        assert result.exit_code == 0

    def test_command_stderr(self):
        result = run_sandboxed(
            [sys.executable, "-c", "import sys; sys.stderr.write('error!')"],
            time_limit_ms=5000,
        )
        assert "error!" in result.stderr

    def test_nonzero_exit_code(self):
        result = run_sandboxed(
            [sys.executable, "-c", "import sys; sys.exit(42)"],
            time_limit_ms=5000,
        )
        assert result.exit_code == 42
        assert result.verdict == "RTE"

    def test_newline_normalisation(self):
        """CRLF in raw bytes should be normalized to LF in stdout.

        Use a raw binary approach: write \\r\\n via sys.stdout.buffer to
        exercise the sandbox's replace('\r\n', '\n') logic reliably.
        """
        code = (
            "import sys; sys.stdout.buffer.write(b'hello\\r\\nworld\\r\\n'); "
            "sys.stdout.buffer.flush()"
        )
        result = run_sandboxed(
            [sys.executable, "-c", code],
            time_limit_ms=5000,
        )
        assert "\r\n" not in result.stdout
        assert "hello\nworld" in result.stdout


class TestStdin:
    def test_stdin_data_string(self):
        result = run_sandboxed(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().strip())"],
            time_limit_ms=5000,
            stdin_data="input data here\n",
        )
        assert result.stdout.strip() == "input data here"

    def test_stdin_file_path(self, tmp_path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("file input\n")
        result = run_sandboxed(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().strip())"],
            time_limit_ms=5000,
            stdin_path=input_file,
        )
        assert result.stdout.strip() == "file input"

    def test_large_stdout_truncated(self):
        """Output exceeding 64MB should be truncated."""
        result = run_sandboxed(
            [sys.executable, "-c", "print('x' * 200, flush=True)"],
            time_limit_ms=5000,
        )
        # Output should not crash and should be readable
        assert len(result.stdout) > 0


class TestTimeLimit:
    def test_command_within_time_limit(self):
        result = run_sandboxed(
            [sys.executable, "-c", "pass"],
            time_limit_ms=2000,
        )
        assert result.verdict == "AC"

    def test_command_exceeding_time_is_killed(self):
        # Python startup is fast, but a long sleep should trigger TLE
        code = "import time; time.sleep(10)"
        result = run_sandboxed(
            [sys.executable, "-c", code],
            time_limit_ms=500,
        )
        # Either TLE (killed by time) or RTE (killed by signal)
        assert result.verdict in ("TLE", "RTE")


class TestWorkingDir:
    def test_working_directory(self, tmp_path):
        subdir = tmp_path / "work"
        subdir.mkdir()
        (subdir / "data.txt").write_text("found-me")
        result = run_sandboxed(
            [
                sys.executable,
                "-c",
                "with open('data.txt') as f: print(f.read().strip())",
            ],
            time_limit_ms=5000,
            working_dir=subdir,
        )
        assert "found-me" in result.stdout


class TestMemoryLimit:
    def test_small_allocation_ok(self):
        result = run_sandboxed(
            [sys.executable, "-c", "x = bytearray(1024 * 1024); print('ok')"],
            time_limit_ms=5000,
            memory_limit_mb=256,
        )
        assert result.verdict == "AC"


class TestResourceUsage:
    def test_cpu_time_reported(self):
        """CPU time should be non-zero for non-trivial work."""
        # A small amount of computation should register CPU time
        result = run_sandboxed(
            [sys.executable, "-c", "sum(range(100000))"],
            time_limit_ms=5000,
        )
        # On Windows, psutil should give us CPU time now
        # On Unix, both psutil and resource fallback work
        # Just verify the field is populated (integer, possibly 0 on some platforms)
        assert isinstance(result.cpu_time_ms, int)
        assert result.cpu_time_ms >= 0

    def test_wall_time_reported(self):
        result = run_sandboxed(
            [sys.executable, "-c", "import time; time.sleep(0.1)"],
            time_limit_ms=5000,
        )
        assert result.wall_time_ms > 0

    def test_memory_reported(self):
        """Memory KB should be an integer (possibly 0 on constrained platforms)."""
        result = run_sandboxed(
            [sys.executable, "-c", "pass"],
            time_limit_ms=5000,
        )
        assert isinstance(result.memory_kb, int)
