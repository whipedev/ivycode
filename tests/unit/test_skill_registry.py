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
    assert definition.risk == "read"
    assert definition.requires_confirmation is False
    assert definition.idempotent is True
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
