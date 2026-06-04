from __future__ import annotations

import json
import zipfile
from pathlib import Path

from light_polygon.db.connection import get_connection
from light_polygon.db.models import Problem, Solution
from light_polygon.problem import layout
from light_polygon.utils.console import console


def export_package(
    slug: str,
    output_path: str | Path = ".",
    format: str = "native",
    all_solutions: bool = False,
) -> Path:
    """Package a problem into a zip file.

    Returns the path to the created zip file.
    """
    problem_dir = layout.problem_dir(slug)
    if not problem_dir.exists():
        raise FileNotFoundError(f"Problem directory not found: {problem_dir}")

    toml_data = layout.read_problem_toml(slug)
    if not toml_data:
        raise FileNotFoundError(f"problem.toml not found for '{slug}'")

    # Resolve output path
    out = Path(output_path)
    if out.is_dir() or str(output_path).endswith(("/", "\\")) or out.suffix == "":
        out = out / f"{slug}-{format}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    # Collect AC solution names if filtering (polygon format default)
    ac_names: set[str] | None = None
    if not all_solutions:
        conn = get_connection()
        try:
            problem = Problem.find_by_slug(conn, slug)
            if problem is not None:
                sols = Solution.find_by_problem(conn, problem.id)
                ac_names = {_resolve_sol_filename(s) for s in sols if s.tag == "AC"}
            # If problem not in DB, ac_names stays None → include all solutions
        finally:
            conn.close()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        st_path = problem_dir / "statement.md"

        if format == "native":
            _add_file(zf, problem_dir / "problem.toml", f"{slug}/problem.toml")
            if st_path.exists():
                _add_file(zf, st_path, f"{slug}/statement.md")
            else:
                console.print(
                    "  [yellow]Warning:[/yellow] statement.md not found, skipping"
                )
            _add_dir(zf, problem_dir / "tests", f"{slug}/tests")
            _add_solutions(zf, problem_dir, slug, None)  # None = all solutions
            _add_toml_if_exists(zf, problem_dir / "tests.toml", f"{slug}/tests.toml")
            _add_dir(zf, problem_dir / "generators", f"{slug}/generators")
            _add_dir(zf, problem_dir / "files", f"{slug}/files")
            print_summary(zf, slug)
        elif format == "polygon":
            if st_path.exists():
                _add_file(zf, st_path, f"{slug}/statement.md")
            else:
                console.print(
                    "  [yellow]Warning:[/yellow] statement.md not found, skipping"
                )
            _add_dir(zf, problem_dir / "tests", f"{slug}/tests")
            _add_solutions(zf, problem_dir, slug, ac_names)
            _add_dir(zf, problem_dir / "files", f"{slug}/files")
            _add_dir(zf, problem_dir / "generators", f"{slug}/generators")
            _add_dir(zf, problem_dir / "checkers", f"{slug}/checkers")
            _add_problem_json(zf, slug, toml_data)
            print_summary(zf, slug)
        else:
            raise ValueError(f"Unknown format '{format}'. Use 'native' or 'polygon'.")

    return out


def _resolve_sol_filename(sol: Solution) -> str:
    return sol.source_path.split("/")[-1]


def _add_file(zf: zipfile.ZipFile, filepath: Path, arcname: str) -> None:
    if filepath.exists():
        zf.write(filepath, arcname)


def _add_dir(zf: zipfile.ZipFile, dirpath: Path, arcprefix: str) -> None:
    if not dirpath.exists() or not dirpath.is_dir():
        return
    for f in sorted(dirpath.iterdir()):
        if f.is_file():
            zf.write(f, f"{arcprefix}/{f.name}")


def _add_toml_if_exists(zf: zipfile.ZipFile, filepath: Path, arcname: str) -> None:
    if filepath.exists():
        zf.write(filepath, arcname)


def _add_solutions(
    zf: zipfile.ZipFile,
    problem_dir: Path,
    slug: str,
    ac_names: set[str] | None,
) -> None:
    sol_dir = problem_dir / "solutions"
    if not sol_dir.exists() or not sol_dir.is_dir():
        return
    for f in sorted(sol_dir.iterdir()):
        if f.is_file():
            if ac_names is not None and f.name not in ac_names:
                continue
            zf.write(f, f"{slug}/solutions/{f.name}")


def _add_problem_json(
    zf: zipfile.ZipFile,
    slug: str,
    toml_data: dict,
) -> None:
    test_dir = layout.problem_dir(slug) / "tests"
    test_count = 0
    if test_dir.exists():
        inputs = set()
        answers = set()
        for f in test_dir.iterdir():
            if not f.is_file():
                continue
            if f.suffix == ".a":
                answers.add(f.stem)  # stem of "01.a" is "01"
            elif f.suffix == "":
                inputs.add(f.stem)  # stem of "01" is "01"
        test_count = len(inputs & answers)

    files_dir = layout.files_dir(slug)
    validator = None
    checker = None
    if files_dir.exists():
        for f in files_dir.iterdir():
            if f.name == "validator.cpp":
                validator = "files/validator.cpp"
            elif f.name == "checker.cpp":
                checker = "files/checker.cpp"

    problem_json = {
        "schema_version": "1.0",
        "name": slug,
        "title": toml_data.get("title", slug),
        "time_limit": toml_data.get("time_limit_ms", 1000),
        "memory_limit": toml_data.get("memory_limit_mb", 256),
        "input_file": toml_data.get("input_file", "stdin"),
        "output_file": toml_data.get("output_file", "stdout"),
        "statement": {"format": "markdown", "path": "statement.md"},
        "test_count": test_count,
        "test_format": {
            "input_pattern": "{index:02d}",
            "answer_pattern": "{index:02d}.a",
        },
        "assets": {
            "validator": validator,
            "checker": checker,
        },
    }
    zf.writestr(
        f"{slug}/problem.json", json.dumps(problem_json, indent=2, ensure_ascii=False)
    )


def print_summary(zf: zipfile.ZipFile, slug: str) -> None:
    names = zf.namelist()
    console.print(f"  [dim]{len(names)} files in {slug}/[/dim]")
    for n in sorted(names):
        console.print(f"    [dim]{n}[/dim]")
