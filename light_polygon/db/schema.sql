-- Light-Polygon Database Schema v1

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password_hash TEXT  NOT NULL,
    display_name TEXT   NOT NULL DEFAULT '',
    role        TEXT    NOT NULL DEFAULT 'author',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS problems (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    slug           TEXT    NOT NULL UNIQUE,
    title          TEXT    NOT NULL,
    time_limit_ms  INTEGER NOT NULL DEFAULT 1000,
    memory_limit_mb INTEGER NOT NULL DEFAULT 256,
    input_file     TEXT    NOT NULL DEFAULT 'stdin',
    output_file    TEXT    NOT NULL DEFAULT 'stdout',
    owner_id       INTEGER NOT NULL REFERENCES users(id),
    is_private     INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_problems_slug ON problems(slug);
CREATE INDEX IF NOT EXISTS idx_problems_owner ON problems(owner_id);

CREATE TABLE IF NOT EXISTS problem_collaborators (
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT    NOT NULL DEFAULT 'editor',
    added_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (problem_id, user_id)
);

CREATE TABLE IF NOT EXISTS statements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id   INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    language     TEXT    NOT NULL DEFAULT 'english',
    title        TEXT    NOT NULL,
    legend       TEXT,
    input_format TEXT,
    output_format TEXT,
    notes        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(problem_id, language)
);

CREATE TABLE IF NOT EXISTS solutions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    language    TEXT    NOT NULL,
    source_path TEXT    NOT NULL,
    tag         TEXT    NOT NULL DEFAULT 'AC',
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(problem_id, name)
);

CREATE TABLE IF NOT EXISTS tests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    test_index  INTEGER NOT NULL,
    testset     TEXT    NOT NULL DEFAULT 'tests',
    description TEXT,
    generator   TEXT,
    is_sample   INTEGER NOT NULL DEFAULT 0,
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(problem_id, testset, test_index)
);

CREATE TABLE IF NOT EXISTS invocations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id    INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    solution_id   INTEGER NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
    test_id       INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    verdict       TEXT    NOT NULL,
    score         REAL    NOT NULL DEFAULT 0.0,
    cpu_time_ms   INTEGER,
    wall_time_ms  INTEGER,
    memory_kb     INTEGER,
    exit_code     INTEGER,
    output_hash   TEXT,
    error_text    TEXT,
    judged_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invocations_solution ON invocations(solution_id);
CREATE INDEX IF NOT EXISTS idx_invocations_test ON invocations(test_id);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS problem_tags (
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (problem_id, tag_id)
);
