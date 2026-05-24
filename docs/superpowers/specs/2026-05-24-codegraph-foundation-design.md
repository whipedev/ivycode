# Ivycode CodeGraph Foundation Design

## Scope

This stage implements `v0.4.0-codegraph-foundation` from `PROMPT_SPEC.md`
section 15, step 4:

- `ivycode/codegraph/service.py`
- `ivycode/codegraph/snapshot.py`
- `ivycode/codegraph/projection.py`

It also wires the existing `ivycode index` CLI command so the CodeGraph can be
visually checked in the terminal.

## Non-Scope

This stage does not implement the file watcher, debounce worker, Router
integration, SubAgent read gates, or multi-language parsing. It implements a
real local Python AST index first, backed by SQLite and FTS5.

## Architecture

`codegraph.projection` parses Python source with `ast` and returns compact
records for symbols, call edges, and FastAPI-style routes.

`codegraph.service` owns the SQLite database at `.ivycode/codegraph.sqlite`,
creates the schema, indexes Python files, searches symbols, resolves impact
radius, lists routes, and returns stats.

`codegraph.snapshot` owns query term extraction, rough token estimation, and
snapshot assembly logic so Router-facing context remains compact.

The CLI command `ivycode index --force` boots `CodeGraphService`, indexes the
current working tree, prints stats, and closes the DB.

## Testing

Tests verify:

- Python AST symbol extraction for functions, classes, methods, calls, and
  FastAPI route decorators.
- SQLite-backed indexing and search.
- Impact radius for direct and transitive callers.
- Snapshot construction with compact relevant symbols/routes.
- CLI `index --force` terminal output.

## Verification

Before commit:

- `python -m pytest -q`
- `python -m ruff check .`
- `python -m mypy ivycode`
- `python -m ivycode doctor`
- `python -m ivycode index --force`
