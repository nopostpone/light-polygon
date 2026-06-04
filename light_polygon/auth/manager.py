from __future__ import annotations

import sqlite3

import bcrypt

from light_polygon.db.models import User


class AuthError(Exception):
    pass


class UserManager:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def register(
        self, username: str, password: str, display_name: str = "", role: str = "author"
    ) -> User:
        existing = User.find_by_username(self.conn, username)
        if existing:
            raise AuthError(f"User '{username}' already exists")
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        return User.create(self.conn, username, password_hash, display_name, role)

    def verify(self, username: str, password: str) -> User:
        user = User.find_by_username(self.conn, username)
        if user is None:
            raise AuthError("Invalid username or password")
        if not bcrypt.checkpw(
            password.encode("utf-8"), user.password_hash.encode("utf-8")
        ):
            raise AuthError("Invalid username or password")
        return user
