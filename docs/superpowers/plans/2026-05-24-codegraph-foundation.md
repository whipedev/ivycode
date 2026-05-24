# CodeGraph Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first SQLite-backed CodeGraph foundation and make `ivycode index --force` visibly useful.

**Architecture:** Parse Python AST into compact DTOs, persist symbols/calls/routes in SQLite + FTS5, expose the CodeGraph facade methods from the spec, and build token-aware graph snapshots for future Router use.

**Tech Stack:** Python 3.11+, `ast`, SQLite/FTS5 via `aiosqlite`, Pydantic v2, Typer, Rich, pytest, ruff, mypy.

---

### Task 1: Projection Parser

**Files:**
- Create: `tests/unit/test_codegraph_projection.py`
- Create: `ivycode/codegraph/__init__.py`
- Create: `ivycode/codegraph/projection.py`

- [x] **Step 1: Write failing tests**

Tests cover function, class, method, call, docstring, signature, and FastAPI
route extraction from Python source.

- [x] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/unit/test_codegraph_projection.py -q`
Expected: FAIL because `ivycode.codegraph.projection` does not exist.

- [x] **Step 3: Implement projection parser**

Create AST extraction helpers and typed Pydantic records.

- [x] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/unit/test_codegraph_projection.py -q`
Expected: PASS.

### Task 2: CodeGraph Service

**Files:**
- Create: `tests/unit/test_codegraph_service.py`
- Create: `ivycode/codegraph/service.py`
- Modify: `pyproject.toml`

- [x] **Step 1: Write failing tests**

Tests cover boot, schema creation, full indexing, search, route listing, impact
radius, and stats.

- [x] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/unit/test_codegraph_service.py -q`
Expected: FAIL because `CodeGraphService` does not exist or dependency is
missing.

- [x] **Step 3: Add dependency**

Add `aiosqlite` to project dependencies and reinstall the editable package.

- [x] **Step 4: Implement service**

Create SQLite schema, index Python files, and expose facade methods.

- [x] **Step 5: Run test to verify pass**

Run: `python -m pytest tests/unit/test_codegraph_service.py -q`
Expected: PASS.

### Task 3: Snapshot Builder

**Files:**
- Create: `tests/unit/test_codegraph_snapshot.py`
- Create: `ivycode/codegraph/snapshot.py`

- [x] **Step 1: Write failing tests**

Tests cover term extraction, route-query detection, token estimation, and
snapshot budget behavior.

- [x] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/unit/test_codegraph_snapshot.py -q`
Expected: FAIL because snapshot helpers do not exist.

- [x] **Step 3: Implement snapshot helpers**

Create compact snapshot assembly helpers used by `CodeGraphService`.

- [x] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/unit/test_codegraph_snapshot.py -q`
Expected: PASS.

### Task 4: CLI Index Command

**Files:**
- Modify: `tests/unit/test_cli.py`
- Modify: `ivycode/cli/app.py`
- Modify: `README.md`
- Modify: `ivycode/__init__.py`

- [x] **Step 1: Write failing tests**

Tests cover `ivycode index --force` terminal output and version
`0.4.0-codegraph-foundation`.

- [x] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: FAIL because `index` still reports the stage boundary.

- [x] **Step 3: Implement CLI command and version bump**

Wire `CodeGraphService` into `index`, update version metadata and README.

- [x] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: PASS.

### Task 5: Verification and Commit

- [x] **Step 1: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy ivycode
python -m ivycode doctor
python -m ivycode index --force
```

Expected: all commands exit with code 0.

- [ ] **Step 2: Commit and push**

Use a multi-paragraph commit message with `What changed`, `Why`, and
`Validation`.
