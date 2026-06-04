from __future__ import annotations


from light_polygon.db.models import Problem, User
from light_polygon.problem.manager import ProblemError, ProblemManager


def test_create_problem(db, logged_in_user):
    mgr = ProblemManager(db)
    problem = mgr.create("test-prob", "Test Problem", logged_in_user.id)
    assert problem.slug == "test-prob"
    assert problem.title == "Test Problem"
    assert problem.owner_id == logged_in_user.id


def test_create_duplicate_slug_fails(db, logged_in_user):
    mgr = ProblemManager(db)
    mgr.create("dup", "First", logged_in_user.id)
    try:
        mgr.create("dup", "Second", logged_in_user.id)
        assert False
    except ProblemError:
        pass


def test_find_by_slug(db, logged_in_user):
    mgr = ProblemManager(db)
    mgr.create("find-me", "Find Me", logged_in_user.id)
    problem = Problem.find_by_slug(db, "find-me")
    assert problem is not None
    assert problem.title == "Find Me"


def test_list_problems(db, logged_in_user):
    mgr = ProblemManager(db)
    mgr.create("prob-a", "A", logged_in_user.id)
    mgr.create("prob-b", "B", logged_in_user.id)
    problems = Problem.list_all(db)
    assert len(problems) == 2


def test_list_problems_by_owner(db, logged_in_user):
    mgr = ProblemManager(db)
    mgr.create("mine", "Mine", logged_in_user.id)
    other = User.create(db, "other", "hash", "Other")
    mgr.create("theirs", "Theirs", other.id)

    mine = Problem.list_all(db, owner_id=logged_in_user.id)
    assert len(mine) == 1
    assert mine[0].slug == "mine"


def test_edit_problem(db, logged_in_user):
    mgr = ProblemManager(db)
    problem = mgr.create("edit-me", "Edit Me", logged_in_user.id)
    problem.title = "Edited Title"
    problem.time_limit_ms = 2000
    problem.save(db)

    reloaded = Problem.find_by_slug(db, "edit-me")
    assert reloaded.title == "Edited Title"
    assert reloaded.time_limit_ms == 2000


def test_delete_problem(db, logged_in_user):
    mgr = ProblemManager(db)
    problem = mgr.create("del-me", "Delete Me", logged_in_user.id)
    problem.delete(db)
    assert Problem.find_by_slug(db, "del-me") is None


def test_problem_directory_created(db, logged_in_user, temp_data_dir):
    mgr = ProblemManager(db)
    mgr.create("dir-test", "Directory Test", logged_in_user.id)
    from light_polygon.problem import layout

    d = layout.problem_dir("dir-test")
    assert d.exists()
    assert (d / "statement.md").exists()
    assert (d / "tests").exists()
    assert (d / "solutions").exists()
