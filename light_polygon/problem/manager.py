from __future__ import annotations

import sqlite3

from light_polygon.db.models import Problem
from light_polygon.problem import layout


class ProblemError(Exception):
    pass


class ProblemManager:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        slug: str,
        title: str,
        owner_id: int,
        time_limit_ms: int = 1000,
        memory_limit_mb: int = 256,
        input_file: str = "stdin",
        output_file: str = "stdout",
        is_private: bool = True,
    ) -> Problem:
        existing = Problem.find_by_slug(self.conn, slug)
        if existing:
            raise ProblemError(f"Problem with slug '{slug}' already exists")

        problem = Problem.create(
            self.conn,
            slug=slug,
            title=title,
            owner_id=owner_id,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
            input_file=input_file,
            output_file=output_file,
        )
        problem.is_private = is_private
        problem.save(self.conn)

        layout.init_problem_dir(
            slug,
            title,
            time_limit_ms,
            memory_limit_mb,
            input_file,
            output_file,
            is_private,
        )
        return problem

    def delete(self, slug: str) -> None:
        problem = Problem.find_by_slug(self.conn, slug)
        if problem is None:
            raise ProblemError(f"Problem '{slug}' not found")
        problem.delete(self.conn)
        layout.remove_problem_dir(slug)
