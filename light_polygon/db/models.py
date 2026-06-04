from __future__ import annotations

import sqlite3
from dataclasses import dataclass


# ─── Row-to-dict helpers ───────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ─── User ──────────────────────────────────────────────────────────

@dataclass
class User:
    id: int | None = None
    username: str = ""
    password_hash: str = ""
    display_name: str = ""
    role: str = "author"

    @classmethod
    def from_row(cls, row: dict) -> User:
        return cls(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            display_name=row.get("display_name", ""),
            role=row.get("role", "author"),
        )

    @classmethod
    def create(cls, conn: sqlite3.Connection, username: str, password_hash: str,
               display_name: str = "", role: str = "author") -> User:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, display_name, role),
        )
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return cls.from_row(dict(row))

    @classmethod
    def find_by_username(cls, conn: sqlite3.Connection, username: str) -> User | None:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    @classmethod
    def find_by_id(cls, conn: sqlite3.Connection, user_id: int) -> User | None:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    @classmethod
    def list_all(cls, conn: sqlite3.Connection) -> list[User]:
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
        return [cls.from_row(dict(r)) for r in rows]


# ─── Problem ───────────────────────────────────────────────────────

@dataclass
class Problem:
    id: int | None = None
    slug: str = ""
    title: str = ""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    input_file: str = "stdin"
    output_file: str = "stdout"
    owner_id: int = 0
    is_private: bool = True

    @classmethod
    def from_row(cls, row: dict) -> Problem:
        return cls(
            id=row["id"],
            slug=row["slug"],
            title=row["title"],
            time_limit_ms=row["time_limit_ms"],
            memory_limit_mb=row["memory_limit_mb"],
            input_file=row["input_file"],
            output_file=row["output_file"],
            owner_id=row["owner_id"],
            is_private=bool(row.get("is_private", 1)),
        )

    @classmethod
    def create(cls, conn: sqlite3.Connection, slug: str, title: str, owner_id: int,
               time_limit_ms: int = 1000, memory_limit_mb: int = 256,
               input_file: str = "stdin", output_file: str = "stdout") -> Problem:
        conn.execute(
            """INSERT INTO problems (slug, title, time_limit_ms, memory_limit_mb,
               input_file, output_file, owner_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, title, time_limit_ms, memory_limit_mb, input_file, output_file, owner_id),
        )
        row = conn.execute("SELECT * FROM problems WHERE slug = ?", (slug,)).fetchone()
        return cls.from_row(dict(row))

    @classmethod
    def find_by_slug(cls, conn: sqlite3.Connection, slug: str) -> Problem | None:
        row = conn.execute("SELECT * FROM problems WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    @classmethod
    def find_by_id(cls, conn: sqlite3.Connection, problem_id: int) -> Problem | None:
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    @classmethod
    def list_all(cls, conn: sqlite3.Connection, owner_id: int | None = None) -> list[Problem]:
        if owner_id is not None:
            rows = conn.execute(
                "SELECT * FROM problems WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM problems ORDER BY created_at DESC"
            ).fetchall()
        return [cls.from_row(dict(r)) for r in rows]

    def save(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """UPDATE problems SET title=?, time_limit_ms=?, memory_limit_mb=?,
               input_file=?, output_file=?, is_private=?, updated_at=datetime('now')
               WHERE id=?""",
            (self.title, self.time_limit_ms, self.memory_limit_mb,
             self.input_file, self.output_file, int(self.is_private), self.id),
        )

    def delete(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM problems WHERE id = ?", (self.id,))


# ─── Solution ──────────────────────────────────────────────────────

@dataclass
class Solution:
    id: int | None = None
    problem_id: int = 0
    name: str = ""
    language: str = "python"
    source_path: str = ""
    tag: str = "AC"
    description: str = ""

    @classmethod
    def from_row(cls, row: dict) -> Solution:
        return cls(
            id=row["id"],
            problem_id=row["problem_id"],
            name=row["name"],
            language=row["language"],
            source_path=row["source_path"],
            tag=row.get("tag", "AC"),
            description=row.get("description", ""),
        )

    @classmethod
    def create(cls, conn: sqlite3.Connection, problem_id: int, name: str,
               language: str, source_path: str, tag: str = "AC",
               description: str = "") -> Solution:
        conn.execute(
            """INSERT INTO solutions (problem_id, name, language, source_path, tag, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (problem_id, name, language, source_path, tag, description),
        )
        row = conn.execute(
            "SELECT * FROM solutions WHERE problem_id = ? AND name = ?",
            (problem_id, name),
        ).fetchone()
        return cls.from_row(dict(row))

    @classmethod
    def find_by_problem(cls, conn: sqlite3.Connection, problem_id: int) -> list[Solution]:
        rows = conn.execute(
            "SELECT * FROM solutions WHERE problem_id = ? ORDER BY name",
            (problem_id,),
        ).fetchall()
        return [cls.from_row(dict(r)) for r in rows]

    @classmethod
    def find_by_id(cls, conn: sqlite3.Connection, solution_id: int) -> Solution | None:
        row = conn.execute("SELECT * FROM solutions WHERE id = ?", (solution_id,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    def save(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE solutions SET tag=?, description=? WHERE id=?",
            (self.tag, self.description, self.id),
        )

    def delete(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM solutions WHERE id = ?", (self.id,))


# ─── Test (test case) ──────────────────────────────────────────────

@dataclass
class TestCase:
    __test__ = False  # Prevent pytest from collecting this as a test class

    id: int | None = None
    problem_id: int = 0
    test_index: int = 0
    testset: str = "tests"
    description: str = ""
    generator: str = ""
    is_sample: bool = False
    verified: bool = False

    @classmethod
    def from_row(cls, row: dict) -> TestCase:
        return cls(
            id=row["id"],
            problem_id=row["problem_id"],
            test_index=row["test_index"],
            testset=row.get("testset", "tests"),
            description=row.get("description", ""),
            generator=row.get("generator", ""),
            is_sample=bool(row.get("is_sample", 0)),
            verified=bool(row.get("verified", 0)),
        )

    @classmethod
    def create(cls, conn: sqlite3.Connection, problem_id: int, test_index: int,
               testset: str = "tests", description: str = "",
               generator: str = "", is_sample: bool = False) -> TestCase:
        conn.execute(
            """INSERT INTO tests (problem_id, test_index, testset, description, generator, is_sample)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (problem_id, test_index, testset, description, generator, int(is_sample)),
        )
        row = conn.execute(
            "SELECT * FROM tests WHERE problem_id = ? AND testset = ? AND test_index = ?",
            (problem_id, testset, test_index),
        ).fetchone()
        return cls.from_row(dict(row))

    @classmethod
    def find_by_problem(cls, conn: sqlite3.Connection, problem_id: int,
                        testset: str | None = None) -> list[TestCase]:
        if testset:
            rows = conn.execute(
                "SELECT * FROM tests WHERE problem_id = ? AND testset = ? ORDER BY test_index",
                (problem_id, testset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tests WHERE problem_id = ? ORDER BY testset, test_index",
                (problem_id,),
            ).fetchall()
        return [cls.from_row(dict(r)) for r in rows]

    @classmethod
    def find_by_id(cls, conn: sqlite3.Connection, test_id: int) -> TestCase | None:
        row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
        if row is None:
            return None
        return cls.from_row(dict(row))

    def save(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE tests SET testset=?, description=?, generator=?, "
            "is_sample=?, verified=? WHERE id=?",
            (self.testset, self.description, self.generator,
             int(self.is_sample), int(self.verified), self.id),
        )

    def delete(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM tests WHERE id = ?", (self.id,))


# ─── Invocation ────────────────────────────────────────────────────

@dataclass
class Invocation:
    id: int | None = None
    problem_id: int = 0
    solution_id: int = 0
    test_id: int = 0
    verdict: str = ""
    score: float = 0.0
    cpu_time_ms: int | None = None
    wall_time_ms: int | None = None
    memory_kb: int | None = None
    exit_code: int | None = None
    output_hash: str = ""
    error_text: str = ""

    @classmethod
    def create(cls, conn: sqlite3.Connection, problem_id: int, solution_id: int,
               test_id: int, verdict: str, score: float = 0.0,
               cpu_time_ms: int | None = None, wall_time_ms: int | None = None,
               memory_kb: int | None = None, exit_code: int | None = None,
               output_hash: str = "", error_text: str = "") -> Invocation:
        conn.execute(
            """INSERT INTO invocations (problem_id, solution_id, test_id, verdict, score,
               cpu_time_ms, wall_time_ms, memory_kb, exit_code, output_hash, error_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (problem_id, solution_id, test_id, verdict, score,
             cpu_time_ms, wall_time_ms, memory_kb, exit_code, output_hash, error_text),
        )
        row = conn.execute(
            "SELECT * FROM invocations WHERE id = last_insert_rowid()"
        ).fetchone()
        return cls.from_row(dict(row))

    @classmethod
    def from_row(cls, row: dict) -> Invocation:
        return cls(
            id=row["id"],
            problem_id=row["problem_id"],
            solution_id=row["solution_id"],
            test_id=row["test_id"],
            verdict=row["verdict"],
            score=row.get("score", 0.0),
            cpu_time_ms=row.get("cpu_time_ms"),
            wall_time_ms=row.get("wall_time_ms"),
            memory_kb=row.get("memory_kb"),
            exit_code=row.get("exit_code"),
            output_hash=row.get("output_hash", ""),
            error_text=row.get("error_text", ""),
        )

    @classmethod
    def find_by_solution(cls, conn: sqlite3.Connection, solution_id: int) -> list[Invocation]:
        rows = conn.execute(
            "SELECT * FROM invocations WHERE solution_id = ? ORDER BY test_id",
            (solution_id,),
        ).fetchall()
        return [cls.from_row(dict(r)) for r in rows]
