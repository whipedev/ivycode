from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, ClassVar

import pytest

from ivycode.agents.mediator import AgentMediator
from ivycode.agents.router import RouterAgent, RouterContext, RouterPlanInvalidError
from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    ExecutionPlan,
    GraphSnapshot,
    Message,
    ModelRef,
    ProviderName,
    StepKind,
    StreamEvent,
)
from ivycode.providers.base import LLMProvider, ToolSchema
from ivycode.skills.builtins import register_builtin_skills
from ivycode.skills.registry import SkillRegistry


class FakeJsonProvider(LLMProvider):
    name: ClassVar[str] = "fake"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def stream(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema] = (),
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        meta: CallerMeta,
    ) -> str:
        self.calls += 1
        return self.responses.pop(0)

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()))


def test_router_local_plan_is_codegraph_first() -> None:
    router = RouterAgent(mediator=_mediator(), skills=_skills())

    plan = router.plan_local(_ctx("Refactor UserAuth login flow"))

    assert plan.steps[0].kind is StepKind.GRAPH_QUERY
    assert plan.steps[0].graph_query is not None
    assert plan.steps[0].graph_query.method == "search_symbols"
    assert plan.steps[1].kind is StepKind.SUBAGENT
    assert plan.steps[1].subagent is not None
    assert plan.steps[1].subagent.agent is AgentName.ARCHITECT
    assert plan.steps[1].depends_on == ["step_01"]
    assert plan.steps[-1].kind is StepKind.AGGREGATE
    assert plan.steps[-1].depends_on == ["step_02"]


def test_router_prompt_render_leaves_no_placeholders() -> None:
    router = RouterAgent(mediator=_mediator(), skills=_skills())

    prompt = router.render_system_prompt(_ctx("Plan auth cleanup"))

    assert "<<<" not in prompt
    assert "ExecutionPlan" in prompt
    assert "Plan auth cleanup" in prompt
    assert "graph.search_symbols" in prompt
    assert "architect" in prompt


def test_router_retries_invalid_provider_json_then_accepts_valid_plan() -> None:
    valid = _valid_plan().model_dump_json()
    provider = FakeJsonProvider(["not-json", '{"summary": 1}', valid])
    router = RouterAgent(
        mediator=_mediator(),
        skills=_skills(),
        provider=provider,
        model=_model(),
    )

    plan = asyncio.run(router.plan(_ctx("Refactor auth")))

    assert provider.calls == 3
    assert plan.summary == _valid_plan().summary


def test_router_raises_after_three_invalid_provider_attempts() -> None:
    provider = FakeJsonProvider(["not-json", "not-json", "not-json"])
    router = RouterAgent(
        mediator=_mediator(),
        skills=_skills(),
        provider=provider,
        model=_model(),
    )

    with pytest.raises(RouterPlanInvalidError):
        asyncio.run(router.plan(_ctx("Refactor auth")))

    assert provider.calls == 3


def _ctx(task: str) -> RouterContext:
    return RouterContext(
        user_task=task,
        snapshot=GraphSnapshot(
            project_root="/repo",
            indexed_files_count=0,
            relevant_symbols=[],
            relevant_routes=[],
            estimated_tokens=1,
        ),
    )


def _mediator() -> AgentMediator:
    return AgentMediator()


def _skills() -> SkillRegistry:
    registry = SkillRegistry()
    register_builtin_skills(registry)
    return registry


def _model() -> ModelRef:
    return ModelRef(
        provider=ProviderName.ANTHROPIC,
        model_id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
    )


def _valid_plan() -> ExecutionPlan:
    return RouterAgent(mediator=_mediator(), skills=_skills()).plan_local(
        _ctx("Refactor auth")
    )
