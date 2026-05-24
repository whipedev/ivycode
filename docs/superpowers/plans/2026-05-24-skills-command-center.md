# Skills Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0.5.0-skills-foundation`: a safe Skills registry, graph/fs builtins, local plugin shell storage, and a polished `ivycode skills` command center.

**Architecture:** Skills are async Python callables registered through a decorator into `SkillRegistry`. Builtins receive a `SkillRuntime` that owns `project_root`, optional `CodeGraphService`, and plugin storage paths. The CLI renders a Rich command center and exposes direct automation-friendly subcommands.

**Tech Stack:** Python 3.11+, Typer, Rich, Pydantic v2, `inspect`, JSON manifests, pytest, ruff, mypy.

---

### Task 1: Skill Registry

**Files:**
- Create: `tests/unit/test_skill_registry.py`
- Create: `ivycode/skills/__init__.py`
- Create: `ivycode/skills/registry.py`

- [x] **Step 1: Write failing registry tests**

```python
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ivycode.skills.registry import SkillRegistry, skill
from ivycode.skills.runtime import SkillRuntime


@skill(
    name="demo.echo",
    description="Echo a value.",
    permissions=["demo:read"],
)
async def echo(runtime: SkillRuntime, value: str, limit: int = 3) -> dict[str, object]:
    return {"root": runtime.project_root.as_posix(), "value": value, "limit": limit}


def test_registry_registers_decorated_async_skill(tmp_path: Path) -> None:
    registry = SkillRegistry()
    registry.register(echo)

    definition = registry.get("demo.echo")

    assert definition.name == "demo.echo"
    assert definition.description == "Echo a value."
    assert definition.permissions == ["demo:read"]
    assert "value" in definition.parameters_schema["properties"]
    assert definition.parameters_schema["required"] == ["value"]

    runtime = SkillRuntime(project_root=tmp_path)
    result = asyncio.run(
        registry.invoke("demo.echo", runtime=runtime, arguments={"value": "ok"})
    )

    assert result == {"root": tmp_path.as_posix(), "value": "ok", "limit": 3}


def test_registry_rejects_duplicate_skill_names() -> None:
    registry = SkillRegistry()
    registry.register(echo)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(echo)
```

- [x] **Step 2: Run registry tests to verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_registry.py -q`

Expected: FAIL because `ivycode.skills.registry` and `SkillRuntime` do not exist.

- [x] **Step 3: Implement minimal registry**

Create `SkillDefinition`, `@skill`, `SkillRegistry.register`, `get`, `list`, and
`invoke`. Generate parameter JSON Schema from the callable signature while
excluding the first `runtime` parameter.

- [x] **Step 4: Run registry tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_registry.py -q`

Expected: PASS.

### Task 2: Skill Runtime And Filesystem Builtins

**Files:**
- Create: `tests/unit/test_skill_fs.py`
- Create: `ivycode/skills/runtime.py`
- Create: `ivycode/skills/builtins/__init__.py`
- Create: `ivycode/skills/builtins/fs.py`

- [x] **Step 1: Write failing filesystem tests**

```python
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ivycode.skills.builtins.fs import read_file, register_fs_skills, write_file
from ivycode.skills.registry import SkillRegistry
from ivycode.skills.runtime import SkillRuntime


def test_read_file_returns_requested_line_range(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    runtime = SkillRuntime(project_root=tmp_path)

    result = asyncio.run(
        read_file(runtime, file_path="app.py", line_start=2, line_end=3)
    )

    assert result == "two\nthree\n"


def test_fs_skills_reject_paths_outside_project(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    runtime = SkillRuntime(project_root=tmp_path)

    with pytest.raises(ValueError, match="outside project root"):
        asyncio.run(read_file(runtime, file_path=outside.as_posix()))

    with pytest.raises(ValueError, match="outside project root"):
        asyncio.run(write_file(runtime, file_path="../outside.txt", content="x"))


def test_register_fs_skills() -> None:
    registry = SkillRegistry()
    register_fs_skills(registry)

    assert registry.get("fs.read_file").permissions == ["fs:read"]
    assert registry.get("fs.write_file").permissions == ["fs:write"]
```

- [x] **Step 2: Run filesystem tests to verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_fs.py -q`

Expected: FAIL because `runtime.py` and `builtins/fs.py` do not exist.

- [x] **Step 3: Implement runtime and fs builtins**

`SkillRuntime` stores `project_root`, optional `codegraph`, and `plugin_root`.
`read_file` supports inclusive one-based line ranges. `write_file` writes only
inside `project_root` and returns a small result dictionary.

- [x] **Step 4: Run filesystem tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_fs.py -q`

Expected: PASS.

### Task 3: Graph Builtins

**Files:**
- Create: `tests/unit/test_skill_graph.py`
- Create: `ivycode/skills/builtins/graph.py`

- [x] **Step 1: Write failing graph tests**

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from ivycode.codegraph import CodeGraphService
from ivycode.skills.builtins.graph import register_graph_skills
from ivycode.skills.registry import SkillRegistry
from ivycode.skills.runtime import SkillRuntime


def test_graph_skills_delegate_to_codegraph(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def authenticate_user(token: str) -> bool:\n    return bool(token)\n",
        encoding="utf-8",
    )

    async def run() -> None:
        codegraph = CodeGraphService()
        await codegraph.boot(tmp_path)
        await codegraph.index(force=True)
        runtime = SkillRuntime(project_root=tmp_path, codegraph=codegraph)
        registry = SkillRegistry()
        register_graph_skills(registry)

        result = await registry.invoke(
            "graph.search_symbols",
            runtime=runtime,
            arguments={"query": "authenticate"},
        )

        assert [symbol.qualified_name for symbol in result] == [
            "app.authenticate_user"
        ]
        assert registry.get("graph.get_impact_radius").permissions == ["graph:read"]
        assert registry.get("graph.get_framework_routes").permissions == ["graph:read"]

        await codegraph.shutdown()

    asyncio.run(run())
```

- [x] **Step 2: Run graph tests to verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_graph.py -q`

Expected: FAIL because `builtins/graph.py` does not exist.

- [x] **Step 3: Implement graph builtins**

Register `graph.search_symbols`, `graph.get_impact_radius`, and
`graph.get_framework_routes`. Each raises a clear `RuntimeError` if the runtime
does not have a booted CodeGraph service.

- [x] **Step 4: Run graph tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_graph.py -q`

Expected: PASS.

### Task 4: Local Plugin Store

**Files:**
- Create: `tests/unit/test_skill_store.py`
- Create: `ivycode/skills/store.py`

- [x] **Step 1: Write failing plugin store tests**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivycode.skills.store import PluginStore


def test_plugin_store_saves_manifest(tmp_path: Path) -> None:
    store = PluginStore(plugin_root=tmp_path / "plugins")

    manifest = store.save_plugin(
        slug="auth-helper",
        description="Auth workflow helper",
        skills=["graph.search_symbols", "fs.read_file"],
    )

    manifest_path = tmp_path / "plugins" / "auth-helper" / "plugin.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest.slug == "auth-helper"
    assert payload["description"] == "Auth workflow helper"
    assert payload["skills"] == ["graph.search_symbols", "fs.read_file"]


def test_plugin_store_rejects_invalid_slug(tmp_path: Path) -> None:
    store = PluginStore(plugin_root=tmp_path / "plugins")

    with pytest.raises(ValueError, match="invalid plugin slug"):
        store.save_plugin(slug="Bad Slug", description="x", skills=["fs.read_file"])
```

- [x] **Step 2: Run store tests to verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_store.py -q`

Expected: FAIL because `store.py` does not exist.

- [x] **Step 3: Implement plugin store**

Use JSON manifests, slug validation, atomic temp directory writes, and rollback
on failure. Include `list_plugins()`.

- [x] **Step 4: Run store tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/unit/test_skill_store.py -q`

Expected: PASS.

### Task 5: CLI Command Center

**Files:**
- Modify: `tests/unit/test_cli.py`
- Create: `tests/unit/test_cli_skills.py`
- Modify: `ivycode/cli/app.py`
- Modify: `ivycode/__init__.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

- [x] **Step 1: Write failing CLI tests**

```python
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ivycode.cli.app import app


def test_skills_dashboard_renders_command_center(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["skills"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "ivycode skills" in result.output
    assert "local command center" in result.output
    assert "graph.search_symbols" in result.output
    assert "fs.read_file" in result.output
    assert "Plugin Shelf" in result.output


def test_skills_save_creates_local_plugin_shell(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HOME", tmp_path.as_posix())
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "skills",
            "save",
            "auth-helper",
            "--skill",
            "graph.search_symbols",
            "--description",
            "Auth helper",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "saved auth-helper" in result.output
    assert (tmp_path / ".ivycode" / "plugins" / "auth-helper" / "plugin.json").exists()
```

Also update `tests/unit/test_cli.py` to expect version `0.5.0` and stage
boundary `v0.5.0-skills-foundation`.

- [x] **Step 2: Run CLI tests to verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py tests/unit/test_cli_skills.py -q`

Expected: FAIL because `skills` command and version bump do not exist.

- [x] **Step 3: Implement CLI command center and version bump**

Add `skills` Typer sub-app with dashboard, `list`, `inspect`, `run`, `save`,
and `plugins`. Bump version to `0.5.0`. Update README current implementation.

- [x] **Step 4: Run CLI tests to verify GREEN**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py tests/unit/test_cli_skills.py -q`

Expected: PASS.

### Task 6: Full Verification And Publish Feature Branch

**Files:**
- Modify: `docs/superpowers/plans/2026-05-24-skills-command-center.md`

- [x] **Step 1: Run full verification**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy ivycode
.venv/bin/python -m ivycode doctor
.venv/bin/python -m ivycode skills
```

Expected: all commands exit with code 0.

- [x] **Step 2: Commit and push feature branch**

Commit title: `feat: add skills command center`

Commit body must include:

- `What changed`
- `Why`
- `Validation`

Push target: `origin feature/skills-command-center`.
