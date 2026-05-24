# UI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first reusable Rich UI foundation for ivycode.

**Architecture:** Create immutable theme tokens, a shared Rich console, a static layout builder, and a basic model message panel. Keep behavior renderable and testable without a running terminal `Live` session.

**Tech Stack:** Python 3.11+, Rich, Pydantic v2, pytest, ruff, mypy.

---

### Task 1: Theme Tokens

**Files:**
- Create: `tests/unit/test_ui_theme.py`
- Create: `ivycode/ui/theme.py`
- Create: `ivycode/ui/__init__.py`

- [ ] **Step 1: Write failing tests**

Tests cover palette values, provider model themes, router theme, and fallback.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_ui_theme.py -q`
Expected: FAIL because `ivycode.ui.theme` does not exist.

- [ ] **Step 3: Implement theme module**

Create `Palette`, `ModelTheme`, `MODEL_THEMES`, `ROUTER_THEME`, and
`theme_for_provider`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_ui_theme.py -q`
Expected: PASS.

### Task 2: Console Singleton

**Files:**
- Create: `tests/unit/test_ui_console.py`
- Create: `ivycode/ui/console.py`

- [ ] **Step 1: Write failing tests**

Tests cover singleton behavior and forced terminal settings.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_ui_console.py -q`
Expected: FAIL because `ivycode.ui.console` does not exist.

- [ ] **Step 3: Implement console module**

Create `get_console()` returning one Rich `Console`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_ui_console.py -q`
Expected: PASS.

### Task 3: Layout Builder

**Files:**
- Create: `tests/unit/test_ui_layout.py`
- Create: `ivycode/ui/layout.py`

- [ ] **Step 1: Write failing tests**

Tests cover named Rich layout regions: header, body, feed, side, activity,
tools, input, footer.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_ui_layout.py -q`
Expected: FAIL because `ivycode.ui.layout` does not exist.

- [ ] **Step 3: Implement layout builder**

Create `build_root_layout()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_ui_layout.py -q`
Expected: PASS.

### Task 4: Basic ModelPanel

**Files:**
- Create: `tests/unit/test_model_panel.py`
- Create: `ivycode/ui/panels/__init__.py`
- Create: `ivycode/ui/panels/model_panel.py`

- [ ] **Step 1: Write failing tests**

Tests render one panel with Rich and assert that model identity and body text
are present.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_model_panel.py -q`
Expected: FAIL because `ivycode.ui.panels.model_panel` does not exist.

- [ ] **Step 3: Implement model panel**

Create `ModelPanel` with `render()` returning a Rich `Group` that follows the
left-bar marker style.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_model_panel.py -q`
Expected: PASS.

### Task 5: Verification and Version Commit

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy ivycode
python -m ivycode doctor
```

Expected: all commands exit with code 0.

- [ ] **Step 2: Commit and push**

Run:

```bash
git add docs ivycode tests
git commit -m "feat: add ui foundation"
git push
```

Expected: commit appears on `origin/main`.
