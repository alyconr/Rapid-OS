# Examples Catalog — RAPID OS Hands-on Labs

This directory contains reproducible, self-contained example projects for the RAPID OS v3 hands-on labs.

## Structure

Each lab includes:
- `starter/`: Initial state of the exercise (base code and initial test suite).
- `solution/`: Canonical reference solution that satisfies all the acceptance criteria.
- `README.md`: Exercise-specific instructions and validation commands.

## Lab catalog

1. [`first-governed-project/`](first-governed-project/README.md) — Task Tracker CLI (Tutorial: [first-governed-project.md](../docs/tutorials/first-governed-project.md)).
2. [`feature-lab/`](feature-lab/README.md) — In-memory booking system with availability control (Tutorial: [feature-lab.md](../docs/tutorials/feature-lab.md)).
3. [`bugfix-lab/`](bugfix-lab/README.md) — Fix for the discount calculation in invoicing (Tutorial: [bugfix-lab.md](../docs/tutorials/bugfix-lab.md)).
4. [`refactor-lab/`](refactor-lab/README.md) — Decoupling the commission calculation (Tutorial: [refactor-lab.md](../docs/tutorials/refactor-lab.md)).
5. [`hardening-lab/`](hardening-lab/README.md) — Hardening and strict input validation (Tutorial: [hardening-lab.md](../docs/tutorials/hardening-lab.md)).
6. [`research-lab/`](research-lab/README.md) — Comparative spike: JSON vs SQLite (Tutorial: [research-lab.md](../docs/tutorials/research-lab.md)).

## Design principle: Zero external dependencies

All the examples use only the Python standard library (`unittest`, `json`, `sqlite3`, `pathlib`, `sys`). They require no external package installation or network connection.
