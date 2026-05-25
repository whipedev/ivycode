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
    write_definition = registry.get("fs.write_file")
    assert write_definition.permissions == ["fs:read", "fs:write"]
    assert write_definition.risk == "write"
    assert write_definition.idempotent is False
