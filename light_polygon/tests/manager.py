from __future__ import annotations

import sqlite3

from light_polygon.db.models import TestCase
from light_polygon.problem import layout


class TestManager:
    def __init__(self, conn: sqlite3.Connection, slug: str) -> None:
        self.conn = conn
        self.slug = slug

    def add(
        self,
        problem_id: int,
        test_index: int,
        input_data: str,
        answer_data: str = "",
        testset: str = "tests",
        description: str = "",
        is_sample: bool = False,
        generator: str = "",
    ) -> TestCase:
        input_path = layout.test_input_path(self.slug, test_index)
        answer_path = layout.test_answer_path(self.slug, test_index)

        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(input_data, encoding="utf-8")

        if answer_data:
            answer_path.write_text(answer_data, encoding="utf-8")
        elif not answer_path.exists():
            answer_path.touch()

        tc = TestCase.create(
            self.conn,
            problem_id=problem_id,
            test_index=test_index,
            testset=testset,
            description=description,
            is_sample=is_sample,
            generator=generator,
        )
        return tc

    def read_input(self, test_index: int) -> str:
        path = layout.test_input_path(self.slug, test_index)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path.read_text(encoding="utf-8")

    def read_answer(self, test_index: int) -> str:
        path = layout.test_answer_path(self.slug, test_index)
        if not path.exists():
            raise FileNotFoundError(f"Answer file not found: {path}")
        return path.read_text(encoding="utf-8")

    def write_answer(self, test_index: int, data: str) -> None:
        path = layout.test_answer_path(self.slug, test_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")

    def delete_files(self, test_index: int) -> None:
        input_path = layout.test_input_path(self.slug, test_index)
        answer_path = layout.test_answer_path(self.slug, test_index)
        if input_path.exists():
            input_path.unlink()
        if answer_path.exists():
            answer_path.unlink()

    def next_index(self, problem_id: int, testset: str = "tests") -> int:
        existing = TestCase.find_by_problem(self.conn, problem_id, testset=testset)
        if not existing:
            return 1
        return max(t.test_index for t in existing) + 1
