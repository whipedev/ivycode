# Skills UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.6.0 as a focused skills UX/UI polish release that brings the v0.5.0 skills command center closer to `PROMPT_SPEC.md` section 4.

**Architecture:** Keep the existing `SkillRegistry`, `SkillRuntime`, and `PluginStore` boundaries. Add presentation helpers in the CLI/UI layer, add honest skill risk metadata to the registry contract, and route skill errors through a Rich error panel.

**Tech Stack:** Python 3.11, Typer, Rich, Pydantic v2, pytest, ruff, mypy strict.

---

### Task 1: Contract Metadata

**Files:**
- Modify: `ivycode/skills/registry.py`
- Modify: `ivycode/skills/builtins/fs.py`
- Modify: `ivycode/skills/builtins/graph.py`
- Test: `tests/unit/test_skill_registry.py`

- [x] Add `risk`, `requires_confirmation`, and `idempotent` fields to `SkillMetadata` and `SkillDefinition`.
- [x] Keep `@skill(...)` backward compatible by giving the new fields defaults.
- [x] Mark graph and read-only file skills as `read`; mark `fs.write_file` as `write`.
- [x] Verify registry tests assert the metadata surfaces through `SkillDefinition`.

### Task 2: Rich Skills List And Inspect

**Files:**
- Modify: `ivycode/cli/app.py`
- Modify: `ivycode/ui/theme.py`
- Test: `tests/unit/test_cli_skills.py`

- [x] Replace the false `Status` column with `Description`, compact permission badges, and a real `Risk` column.
- [x] Add namespace glyphs for `fs.*`, `graph.*`, and `plugin.*`.
- [x] Render `skills inspect <name>` as description, permissions, parameter table, and usage.
- [x] Keep raw JSON Schema available behind `--schema`.

### Task 3: Skill Run UX And Errors

**Files:**
- Modify: `ivycode/cli/app.py`
- Create: `ivycode/ui/panels/error_panel.py`
- Modify: `ivycode/ui/panels/__init__.py`
- Test: `tests/unit/test_cli_skills.py`

- [x] Add `--json` to `skills run` for strict machine-readable output.
- [x] Wrap human `skills run` with Rich `Status` using `ivy-orbit`.
- [x] Render success with skill name, duration, and a human result view.
- [x] Catch skill exceptions and render an error panel with `✗`, exception type, message, and arguments.

### Task 4: Safe Plugin Save

**Files:**
- Modify: `ivycode/cli/app.py`
- Modify: `ivycode/skills/store.py`
- Test: `tests/unit/test_cli_skills.py`

- [x] Check an existing plugin slug before save and return a `typer.BadParameter`.
- [x] Require confirmation for `skills save` unless `--yes` is passed.
- [x] Add `created_at` to new manifests while accepting existing manifests without it.
- [x] Expand the plugins table with description, validity, and path.

### Task 5: Version, Docs, Screenshots, Verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `ivycode/__init__.py`
- Modify: `README.md`
- Create: `docs/screenshots/skills-v0.6.0/*.txt`

- [x] Bump version from `0.5.0` to `0.6.0`.
- [x] Update README Current implementation to `v0.6.0-skills-ui-polish`.
- [x] Capture text screenshots for `skills list`, `skills inspect fs.write_file`, and `skills run fs.read_file`.
- [x] Run `pytest`, `ruff`, `mypy`, `doctor`, and manual CLI smoke checks before commit.
