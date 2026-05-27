from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ivycode.agents.mediator import AgentMediator
from ivycode.agents.subagents.architect import ARCHITECT_REPORT_SCHEMA
from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    ExecutionPlan,
    GraphQuery,
    GraphSnapshot,
    IvyBaseModel,
    ModelRef,
    PlanStep,
    StepKind,
    SubAgentDirective,
)
from ivycode.core.settings import DEFAULT_ROUTER_MODEL
from ivycode.providers.base import LLMProvider
from ivycode.skills.registry import SkillRegistry

_ROUTER_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "router.md"
_ARCHITECT_SENTENCE = (
    "Return ONLY a JSON object matching the provided schema. "
    "Any deviation will be rejected."
)


class RouterContext(IvyBaseModel):
    user_task: str
    snapshot: GraphSnapshot
    validation_error: str | None = None

    def with_validation_error(self, error: str) -> RouterContext:
        return self.model_copy(update={"validation_error": error})


class RouterPlanInvalidError(ValueError):
    def __init__(self, *, errors: list[dict[str, Any]], raw_output: str) -> None:
        super().__init__("router returned an invalid ExecutionPlan")
        self.errors = errors
        self.raw_output = raw_output


class RouterAgent:
    def __init__(
        self,
        *,
        mediator: AgentMediator,
        skills: SkillRegistry,
        provider: LLMProvider | None = None,
        model: ModelRef = DEFAULT_ROUTER_MODEL,
        prompt_path: Path = _ROUTER_PROMPT_PATH,
    ) -> None:
        self._mediator = mediator
        self._skills = skills
        self._provider = provider
        self._model = model
        self._prompt_template = prompt_path.read_text(encoding="utf-8")

    async def plan(self, ctx: RouterContext) -> ExecutionPlan:
        if self._provider is None:
            return self.plan_local(ctx)

        raw = ""
        current_ctx = ctx
        for attempt in range(3):
            raw = await self._provider.complete_json(
                system=self.render_system_prompt(current_ctx),
                user="Produce the ExecutionPlan now.",
                response_schema=ExecutionPlan.model_json_schema(),
                meta=CallerMeta(agent=AgentName.ROUTER, model=self._model),
            )
            try:
                return ExecutionPlan.model_validate_json(raw, strict=True)
            except (ValidationError, ValueError) as exc:
                if attempt == 2:
                    raise RouterPlanInvalidError(
                        errors=_validation_errors(exc),
                        raw_output=raw,
                    ) from exc
                current_ctx = current_ctx.with_validation_error(str(exc))
        raise AssertionError("unreachable")

    def plan_local(self, ctx: RouterContext) -> ExecutionPlan:
        return ExecutionPlan(
            summary=f"Plan for {ctx.user_task} grounded in the local CodeGraph.",
            risk_level=_risk_level(ctx.user_task),
            estimated_total_tokens=8000,
            steps=[
                PlanStep(
                    id="step_01",
                    kind=StepKind.GRAPH_QUERY,
                    rationale=(
                        "Ground the request in CodeGraph symbols before delegation."
                    ),
                    graph_query=GraphQuery(
                        method="search_symbols",
                        arguments={"query": ctx.user_task, "limit": 20},
                    ),
                ),
                PlanStep(
                    id="step_02",
                    kind=StepKind.SUBAGENT,
                    rationale=(
                        "Ask the Architect subagent for a grounded "
                        "implementation shape."
                    ),
                    depends_on=["step_01"],
                    subagent=SubAgentDirective(
                        agent=AgentName.ARCHITECT,
                        instructions=(
                            "Analyze architecture impact using CodeGraph references "
                            f"for this task: {ctx.user_task}. {_ARCHITECT_SENTENCE}"
                        ),
                        inputs={
                            "user_task": ctx.user_task,
                            "graph_snapshot": ctx.snapshot.model_dump(mode="json"),
                            "graph_step": "step_01",
                        },
                        allowed_skills=[
                            "graph.search_symbols",
                            "graph.get_impact_radius",
                            "graph.get_framework_routes",
                            "fs.read_file",
                        ],
                        token_budget=6000,
                        expected_output_schema=ARCHITECT_REPORT_SCHEMA,
                    ),
                ),
                PlanStep(
                    id="step_03",
                    kind=StepKind.AGGREGATE,
                    rationale=(
                        "Aggregate graph and architect outputs into a final answer."
                    ),
                    depends_on=["step_02"],
                ),
            ],
            final_aggregator=AgentName.ROUTER,
        )

    def render_system_prompt(self, ctx: RouterContext) -> str:
        prompt = (
            self._prompt_template.replace(
                "<<<schema:ExecutionPlan>>>",
                json.dumps(ExecutionPlan.model_json_schema(), indent=2),
            )
            .replace("<<<user_task>>>", ctx.user_task)
            .replace(
                "<<<graph_snapshot_json>>>",
                ctx.snapshot.model_dump_json(indent=2),
            )
            .replace(
                "<<<subagents_registry_json>>>",
                self._mediator.describe_subagents_json(),
            )
            .replace("<<<skills_registry_json>>>", _skills_registry_json(self._skills))
        )
        if ctx.validation_error is not None:
            prompt += f"\n\n# PREVIOUS VALIDATION ERROR\n{ctx.validation_error}\n"
        return prompt


def _skills_registry_json(skills: SkillRegistry) -> str:
    payload = [
        {
            "name": definition.name,
            "description": definition.description,
            "permissions": definition.permissions,
            "risk": definition.risk,
            "parameters_schema": definition.parameters_schema,
        }
        for definition in skills.list()
    ]
    return json.dumps(payload, indent=2)


def _risk_level(task: str) -> str:
    lowered = task.lower()
    if any(term in lowered for term in ("auth", "payment", "database", "persistence")):
        return "high"
    if any(term in lowered for term in ("refactor", "write", "change", "implement")):
        return "medium"
    return "low"


def _validation_errors(exc: Exception) -> list[dict[str, Any]]:
    if isinstance(exc, ValidationError):
        return [dict(error) for error in exc.errors()]
    return [{"type": type(exc).__name__, "msg": str(exc)}]
