from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ivycode.agents.base import AgentContext
from ivycode.agents.mediator import AgentMediator, AgentMediatorError
from ivycode.agents.router import RouterAgent, RouterContext
from ivycode.agents.subagents.architect import ArchitectSubAgent
from ivycode.codegraph import CodeGraphService
from ivycode.core.envelope import GraphSnapshot, StepKind
from ivycode.skills.builtins import register_builtin_skills
from ivycode.skills.registry import SkillRegistry


def test_mediator_dispatches_graph_subagent_and_aggregate_steps(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def login_user() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )

    async def run() -> list[str]:
        codegraph = CodeGraphService()
        await codegraph.boot(tmp_path)
        try:
            await codegraph.index(force=True)
            skills = _skills()
            mediator = AgentMediator()
            mediator.register(ArchitectSubAgent())
            plan = RouterAgent(mediator=mediator, skills=skills).plan_local(
                RouterContext(
                    user_task="Refactor login_user",
                    snapshot=await codegraph.snapshot_for("login_user"),
                )
            )
            context = AgentContext(
                project_root=tmp_path,
                skills=skills,
                codegraph=codegraph,
                previous_results={},
            )
            results = await mediator.dispatch(plan, context=context)
            return [result.step_id for result in results]
        finally:
            await codegraph.shutdown()

    assert asyncio.run(run()) == ["step_01", "step_02", "step_03"]


def test_mediator_rejects_unknown_dependencies(tmp_path: Path) -> None:
    skills = _skills()
    mediator = AgentMediator()
    plan = RouterAgent(mediator=mediator, skills=skills).plan_local(
        RouterContext(
            user_task="Refactor login",
            snapshot=GraphSnapshot(
                project_root=tmp_path.as_posix(),
                indexed_files_count=0,
                relevant_symbols=[],
                relevant_routes=[],
                estimated_tokens=1,
            ),
        )
    )
    broken_step = plan.steps[1].model_copy(update={"depends_on": ["step_99"]})
    broken_plan = plan.model_copy(
        update={"steps": [plan.steps[0], broken_step, plan.steps[2]]}
    )
    context = AgentContext(project_root=tmp_path, skills=skills, previous_results={})

    with pytest.raises(AgentMediatorError, match="unknown dependency"):
        asyncio.run(mediator.dispatch(broken_plan, context=context))


def test_mediator_describes_registered_subagents() -> None:
    mediator = AgentMediator()
    mediator.register(ArchitectSubAgent())

    description = mediator.describe_subagents_json()

    assert "architect" in description
    assert "Architecture planning" in description


def test_router_plan_uses_only_stage_six_step_kinds() -> None:
    plan = RouterAgent(mediator=AgentMediator(), skills=_skills()).plan_local(
        RouterContext(
            user_task="Refactor login",
            snapshot=GraphSnapshot(
                project_root="/repo",
                indexed_files_count=0,
                relevant_symbols=[],
                relevant_routes=[],
                estimated_tokens=1,
            ),
        )
    )

    assert [step.kind for step in plan.steps] == [
        StepKind.GRAPH_QUERY,
        StepKind.SUBAGENT,
        StepKind.AGGREGATE,
    ]


def _skills() -> SkillRegistry:
    registry = SkillRegistry()
    register_builtin_skills(registry)
    return registry
