from __future__ import annotations

from typing import Any

from ivycode.skills.registry import SkillRegistry, skill
from ivycode.skills.runtime import SkillRuntime


@skill(
    name="fs.read_file",
    description="Read a project file, optionally restricted to a line range.",
    permissions=["fs:read"],
)
async def read_file(
    runtime: SkillRuntime,
    file_path: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> str:
    path = runtime.resolve_project_path(file_path)
    content = path.read_text(encoding="utf-8")
    if line_start is None and line_end is None:
        return content
    if line_start is None or line_end is None:
        raise ValueError("line_start and line_end must be provided together")
    if line_start < 1:
        raise ValueError("line_start must be >= 1")
    if line_end < line_start:
        raise ValueError("line_end must be >= line_start")

    lines = content.splitlines(keepends=True)
    return "".join(lines[line_start - 1 : line_end])


@skill(
    name="fs.write_file",
    description="Write a project file inside the current project root.",
    permissions=["fs:write"],
)
async def write_file(
    runtime: SkillRuntime,
    file_path: str,
    content: str,
) -> dict[str, Any]:
    path = runtime.resolve_project_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "file_path": path.relative_to(runtime.project_root).as_posix(),
        "bytes_written": len(content.encode("utf-8")),
    }


def register_fs_skills(registry: SkillRegistry) -> None:
    registry.register(read_file)
    registry.register(write_file)
