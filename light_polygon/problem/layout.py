from __future__ import annotations

from pathlib import Path

import tomli_w
import tomllib

from light_polygon.config import get_config


def problem_dir(slug: str) -> Path:
    return get_config().problems_dir / slug


def problem_toml_path(slug: str) -> Path:
    return problem_dir(slug) / "problem.toml"


def statement_path(slug: str) -> Path:
    return problem_dir(slug) / "statement.md"


def tests_dir(slug: str) -> Path:
    return problem_dir(slug) / "tests"


def test_input_path(slug: str, test_index: int) -> Path:
    return tests_dir(slug) / f"{test_index:02d}"


def test_answer_path(slug: str, test_index: int) -> Path:
    return tests_dir(slug) / f"{test_index:02d}.a"


def solutions_dir(slug: str) -> Path:
    return problem_dir(slug) / "solutions"


def files_dir(slug: str) -> Path:
    return problem_dir(slug) / "files"


def tests_toml_path(slug: str) -> Path:
    return problem_dir(slug) / "tests.toml"


def generators_dir(slug: str) -> Path:
    return problem_dir(slug) / "generators"


def checkers_dir(slug: str) -> Path:
    return problem_dir(slug) / "checkers"


def init_problem_dir(
    slug: str,
    title: str,
    time_limit_ms: int = 1000,
    memory_limit_mb: int = 256,
    input_file: str = "stdin",
    output_file: str = "stdout",
    is_private: bool = True,
) -> Path:
    root = problem_dir(slug)
    for d in [
        root,
        tests_dir(slug),
        solutions_dir(slug),
        files_dir(slug),
        generators_dir(slug),
    ]:
        d.mkdir(parents=True, exist_ok=True)

    toml_data = {
        "slug": slug,
        "title": title,
        "time_limit_ms": time_limit_ms,
        "memory_limit_mb": memory_limit_mb,
        "input_file": input_file,
        "output_file": output_file,
        "is_private": is_private,
    }
    with open(problem_toml_path(slug), "wb") as f:
        tomli_w.dump(toml_data, f)

    st = statement_path(slug)
    if not st.exists():
        st.write_text(
            f"# {title}\n\n## Description\n\n## Input\n\n## Output\n\n## Examples\n\n## Notes\n",
            encoding="utf-8",
        )

    return root


def read_problem_toml(slug: str) -> dict:
    path = problem_toml_path(slug)
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def write_problem_toml(slug: str, data: dict) -> None:
    path = problem_toml_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def remove_problem_dir(slug: str) -> None:
    import shutil

    root = problem_dir(slug)
    if root.exists():
        shutil.rmtree(root)
