# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Python package foundation for ivycode.

**Architecture:** Implement immutable Pydantic contracts in `ivycode.core.envelope`, runtime settings in `ivycode.core.settings`, and a minimal Typer CLI that can run `doctor`. Keep stage-one behavior explicit and non-fake.

**Tech Stack:** Python 3.11+, Pydantic v2, pydantic-settings, Typer, Rich, pytest, ruff, mypy.

---

### Task 1: Project Metadata

**Files:**
- Create: `pyproject.toml`
- Create: `ivycode/py.typed`

- [ ] **Step 1: Write project metadata**

Create package metadata, dependencies, console script, and strict tool configs.

- [ ] **Step 2: Verify metadata parses**

Run: `python -m pip install -e ".[dev]"`
Expected: project installs into the active environment.

### Task 2: Core Envelope Contracts

**Files:**
- Create: `tests/unit/test_envelope.py`
- Create: `ivycode/core/envelope.py`
- Create: `ivycode/core/__init__.py`

- [ ] **Step 1: Write failing tests**

Tests cover immutable models, forbidden extra fields, UTC timestamps, plan-step
validation, and execution-plan serialization.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_envelope.py -q`
Expected: FAIL because `ivycode.core.envelope` does not exist.

- [ ] **Step 3: Implement contracts**

Implement the models described in `PROMPT_SPEC.md` section 2.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_envelope.py -q`
Expected: PASS.

### Task 3: Settings

**Files:**
- Create: `tests/unit/test_settings.py`
- Create: `ivycode/core/settings.py`

- [ ] **Step 1: Write failing tests**

Tests cover default router model, optional missing API keys, default paths, and
default concurrency and timeout values.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_settings.py -q`
Expected: FAIL because `ivycode.core.settings` does not exist.

- [ ] **Step 3: Implement settings**

Implement `Settings` with `IVYCODE_` environment prefix, `.env`, and
`~/.ivycode/config.toml` metadata.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_settings.py -q`
Expected: PASS.

### Task 4: CLI Entrypoint

**Files:**
- Create: `tests/unit/test_cli.py`
- Create: `ivycode/__init__.py`
- Create: `ivycode/__main__.py`
- Create: `ivycode/cli/__init__.py`
- Create: `ivycode/cli/app.py`

- [ ] **Step 1: Write failing tests**

Tests cover `doctor`, package version, and explicit non-implemented command
diagnostics.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: FAIL because CLI modules do not exist.

- [ ] **Step 3: Implement CLI**

Implement `doctor`, `chat`, `plan`, and `index` commands. Only `doctor` reports
stage-one status; the other commands exit with explicit stage diagnostics.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_cli.py -q`
Expected: PASS.

### Task 5: Verification and Version Commit

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document the stage-one commands and verification commands.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy ivycode
python -m ivycode doctor
```

Expected: all commands exit with code 0.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add pyproject.toml README.md docs ivycode tests PROMPT_SPEC.md
git commit -m "feat: add foundation package"
git push
```

Expected: commit appears on `origin/main`.
