from __future__ import annotations

from light_polygon.auth.manager import AuthError, UserManager
from light_polygon.db.models import User


def test_register_user(db):
    mgr = UserManager(db)
    user = mgr.register("alice", "password123", "Alice")
    assert user.username == "alice"
    assert user.display_name == "Alice"
    assert user.id is not None


def test_register_duplicate_fails(db):
    mgr = UserManager(db)
    mgr.register("bob", "password123")
    try:
        mgr.register("bob", "otherpassword")
        assert False, "Should have raised"
    except AuthError:
        pass


def test_verify_correct_password(db):
    mgr = UserManager(db)
    mgr.register("carol", "secret")
    user = mgr.verify("carol", "secret")
    assert user.username == "carol"


def test_verify_wrong_password(db):
    mgr = UserManager(db)
    mgr.register("dave", "secret")
    try:
        mgr.verify("dave", "wrong")
        assert False
    except AuthError:
        pass


def test_find_by_username(db):
    mgr = UserManager(db)
    mgr.register("eve", "pass")
    user = User.find_by_username(db, "eve")
    assert user is not None
    assert user.username == "eve"


def test_list_users(db):
    mgr = UserManager(db)
    mgr.register("user1", "pass")
    mgr.register("user2", "pass")
    users = User.list_all(db)
    assert len(users) == 2
