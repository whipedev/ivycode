from __future__ import annotations

from ivycode.codegraph import CodeGraphService
from ivycode.core.envelope import FrameworkRoute, ImpactReport, SymbolBrief
from ivycode.skills.registry import SkillRegistry, skill
from ivycode.skills.runtime import SkillRuntime


@skill(
    name="graph.search_symbols",
    description="Search code symbols by name using the local CodeGraph index.",
    permissions=["graph:read"],
)
async def search_symbols(
    runtime: SkillRuntime,
    query: str,
    limit: int = 20,
) -> list[SymbolBrief]:
    codegraph = _codegraph(runtime)
    return await codegraph.search_symbols(query, limit=limit)


@skill(
    name="graph.get_impact_radius",
    description="Find direct and transitive callers for a CodeGraph symbol.",
    permissions=["graph:read"],
)
async def get_impact_radius(
    runtime: SkillRuntime,
    symbol: str,
) -> ImpactReport:
    codegraph = _codegraph(runtime)
    return await codegraph.get_impact_radius(symbol)


@skill(
    name="graph.get_framework_routes",
    description="List framework routes discovered by CodeGraph.",
    permissions=["graph:read"],
)
async def get_framework_routes(
    runtime: SkillRuntime,
    framework: str | None = None,
) -> list[FrameworkRoute]:
    codegraph = _codegraph(runtime)
    return await codegraph.get_framework_routes(framework=framework)


def register_graph_skills(registry: SkillRegistry) -> None:
    registry.register(search_symbols)
    registry.register(get_impact_radius)
    registry.register(get_framework_routes)


def _codegraph(runtime: SkillRuntime) -> CodeGraphService:
    if runtime.codegraph is None:
        raise RuntimeError("CodeGraphService is not available in this SkillRuntime")
    return runtime.codegraph
