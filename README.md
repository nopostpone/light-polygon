# light-polygon

[中文版本](docs/README.zh.md)

> **🚧 Work in Progress — This project is NOT yet ready for production use.**
> 
> The architecture is currently undergoing a major refactor. APIs, directory structures, and commands may change significantly. Use at your own risk.

A lightweight CLI tool for algorithm competition problem preparation, inspired by [Codeforces Polygon](https://polygon.codeforces.com/).

Fully offline, all data stored locally. Designed for individual problem setters and small teams.

## Quick Start

```bash
# 1. Register an account
lp user register alice

# 2. Log in
lp user login alice

# 3. Create a problem
lp problem create two-sum --title "Two Sum" --tl 2000 --ml 512

# 4. Edit the statement (Markdown + LaTeX math)
lp statement edit two-sum

# 5. Add a reference solution
lp solution add two-sum solve.cpp --tag AC

# 6. Add test cases
lp test add two-sum --input 1.in --answer 1.out --sample --desc "Sample 1"

# 7. Judge solutions against tests
lp judge run two-sum

# 8. Export the statement
lp statement export two-sum --format html
```

## Features

- **User management** — Multi-user registration and login, data isolation
- **Problem management** — Create, edit, delete problems with time/memory limits
- **Statement editor** — Markdown + LaTeX math, export to HTML or LaTeX
- **Solution management** — Upload multiple solutions with verdict tags (AC, WA, TLE, etc.)
- **Test generation** — Manual test cases or auto-generated via C++ generators (testlib.h)
- **Input validation** — Optional validator.cpp to check generated test data
- **Judging engine** — Sandboxed execution, output comparison, summary reports
- **Package export** — One-click zip export, Polygon-compatible format supported

## Commands

| Command | Description |
|---------|-------------|
| `lp user register/list/login/logout/whoami` | User management |
| `lp problem create/list/info/edit/delete` | Problem management |
| `lp statement edit/preview/export` | Statement editing & export |
| `lp solution add/list/delete/tag` | Solution management |
| `lp test add/list/delete/sample` | Test case management |
| `lp test gen-config/generate` | Automated test generation |
| `lp judge run/history` | Judging & evaluation |
| `lp export package` | Package export |

## License

MIT
