from __future__ import annotations

from datetime import UTC
from uuid import UUID

import pytest
from pydantic import ValidationError

from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    ExecutionPlan,
    GraphQuery,
    Message,
    ModelRef,
    PlanStep,
    ProviderName,
    Role,
    StepKind,
    SubAgentDirective,
    UsageMetrics,
)


def test_model_ref_forbids_extra_fields_and_is_frozen() -> None:
    model = ModelRef(
        provider=ProviderName.ANTHROPIC,
        model_id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
    )

    with pytest.raises(ValidationError):
        ModelRef.model_validate(
            {
                "provider": "anthropic",
                "model_id": "claude-opus-4-7",
                "display_name": "Claude Opus 4.7",
                "extra": "rejected",
            }
        )

    with pytest.raises(ValidationError):
        model.model_id = "other"  # type: ignore[misc]


def test_caller_meta_creates_uuid_ids_and_utc_timestamp() -> None:
    model = ModelRef(
        provider=ProviderName.OPENAI,
        model_id="gpt-5.5-xhigh",
        display_name="GPT-5.5 xhigh",
    )
    meta = CallerMeta(agent=AgentName.ROUTER, model=model)

    assert isinstance(meta.trace_id, UUID)
    assert isinstance(meta.span_id, UUID)
    assert meta.initiated_at.tzinfo is not None
    assert meta.initiated_at.utcoffset() == UTC.utcoffset(meta.initiated_at)


def test_message_requires_caller_meta() -> None:
    model = ModelRef(
        provider=ProviderName.GOOGLE,
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
    )
    meta = CallerMeta(agent=AgentName.ARCHITECT, model=model)

    message = Message(role=Role.USER, content="Index this project.", meta=meta)

    assert message.meta.agent is AgentName.ARCHITECT
    assert message.tool_calls == []
    assert message.tool_result is None

    with pytest.raises(ValidationError):
        Message.model_validate({"role": "user", "content": "missing meta"})


def test_plan_step_requires_payload_matching_kind() -> None:
    graph_step = PlanStep(
        id="step_01",
        kind=StepKind.GRAPH_QUERY,
        rationale="Ground the request in local CodeGraph symbols.",
        graph_query=GraphQuery(method="search_symbols", arguments={"query": "auth"}),
    )

    assert graph_step.graph_query is not None
    assert graph_step.subagent is None

    with pytest.raises(ValidationError):
        PlanStep(
            id="step_02",
            kind=StepKind.GRAPH_QUERY,
            rationale="This carries the wrong payload for its declared kind.",
            subagent=SubAgentDirective(
                agent=AgentName.TESTER,
                instructions=(
                    "Write tests for the impacted symbols. Return ONLY a JSON "
                    "object matching the provided schema. Any deviation will be "
                    "rejected."
                ),
                inputs={},
            ),
        )

    with pytest.raises(ValidationError):
        PlanStep(
            id="step_03",
            kind=StepKind.SUBAGENT,
            rationale="This carries too many payloads at the same time.",
            graph_query=GraphQuery(
                method="search_symbols",
                arguments={"query": "auth"},
            ),
            subagent=SubAgentDirective(
                agent=AgentName.TESTER,
                instructions=(
                    "Write tests for the impacted symbols. Return ONLY a JSON "
                    "object matching the provided schema. Any deviation will be "
                    "rejected."
                ),
                inputs={},
            ),
        )


def test_execution_plan_round_trips_with_strict_json_validation() -> None:
    plan = ExecutionPlan(
        summary="Search graph context before dispatching a tester subagent.",
        risk_level="low",
        estimated_total_tokens=1200,
        steps=[
            PlanStep(
                id="step_01",
                kind=StepKind.GRAPH_QUERY,
                rationale="Find relevant symbols before touching source files.",
                graph_query=GraphQuery(
                    method="search_symbols",
                    arguments={"query": "login", "limit": 10},
                ),
            )
        ],
        final_aggregator=AgentName.ROUTER,
    )

    restored = ExecutionPlan.model_validate_json(plan.model_dump_json(), strict=True)

    assert restored == plan


def test_usage_metrics_requires_positive_token_counts() -> None:
    with pytest.raises(ValidationError):
        UsageMetrics(input_tokens=0, output_tokens=1, cost_usd=0, latency_ms=1)
