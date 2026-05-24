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
