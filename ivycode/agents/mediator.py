from __future__ import annotations

import json
from time import perf_counter

from ivycode.agents.base import AgentContext, SubAgent, jsonable
from ivycode.core.envelope import (
    AgentName,
    ExecutionPlan,
    GraphQuery,
    PlanStep,
    StepKind,
    StepResult,
)


class AgentMediatorError(RuntimeError):
    pass


class AgentMediator:
    def __init__(self) -> None:
        self._subagents: dict[AgentName, SubAgent] = {}

    def register(self, subagent: SubAgent) -> None:
        if subagent.name in self._subagents:
            raise AgentMediatorError(f"subagent already registered: {subagent.name}")
        self._subagents[subagent.name] = subagent

    def describe_subagents(self) -> list[dict[str, object]]:
        return [
            self._subagents[name].describe()
            for name in sorted(self._subagents, key=lambda item: item.value)
        ]

    def describe_subagents_json(self) -> str:
        return json.dumps(self.describe_subagents(), indent=2)

    async def dispatch(
        self,
        plan: ExecutionPlan,
        *,
        context: AgentContext,
    ) -> list[StepResult]:
        self._validate_plan_dependencies(plan)
        completed: dict[str, StepResult] = dict(context.previous_results)
        ordered_results: list[StepResult] = []
        for step in plan.steps:
            self._validate_dependencies(step, completed)
            dispatch_context = AgentContext(
                project_root=context.project_root,
                skills=context.skills,
                codegraph=context.codegraph,
                previous_results=completed,
            )
            result = await self.dispatch_step(step, context=dispatch_context)
            completed[step.id] = result
            ordered_results.append(result)
        return ordered_results

    async def dispatch_step(
        self,
        step: PlanStep,
        *,
        context: AgentContext,
    ) -> StepResult:
        if step.kind is StepKind.GRAPH_QUERY:
            if step.graph_query is None:
                raise AgentMediatorError(f"missing graph query payload: {step.id}")
            return await self._dispatch_graph_query(step.id, step.graph_query, context)
        if step.kind is StepKind.SUBAGENT:
            if step.subagent is None:
                raise AgentMediatorError(f"missing subagent payload: {step.id}")
            subagent = self._subagents.get(step.subagent.agent)
            if subagent is None:
                raise AgentMediatorError(f"unknown subagent: {step.subagent.agent}")
            return await subagent.execute(
                step_id=step.id,
                directive=step.subagent,
                context=context,
            )
        if step.kind is StepKind.AGGREGATE:
            return self._aggregate(step.id, context)
        raise AgentMediatorError("parallel_compare dispatch is reserved for Stage 7")

    def _validate_dependencies(
        self,
        step: PlanStep,
        completed: dict[str, StepResult],
    ) -> None:
        for dependency in step.depends_on:
            if dependency not in completed:
                raise AgentMediatorError(
                    f"unknown dependency for {step.id}: {dependency}"
                )

    def _validate_plan_dependencies(self, plan: ExecutionPlan) -> None:
        known: set[str] = set()
        all_ids = {step.id for step in plan.steps}
        for step in plan.steps:
            for dependency in step.depends_on:
                if dependency not in all_ids:
                    raise AgentMediatorError(
                        f"unknown dependency for {step.id}: {dependency}"
                    )
                if dependency not in known:
                    raise AgentMediatorError(
                        f"forward dependency for {step.id}: {dependency}"
                    )
            known.add(step.id)

    async def _dispatch_graph_query(
        self,
        step_id: str,
        query: GraphQuery,
        context: AgentContext,
    ) -> StepResult:
        if context.codegraph is None:
            raise AgentMediatorError("CodeGraphService is required for graph_query")

        started = perf_counter()
        result: object
        if query.method == "search_symbols":
            result = await context.codegraph.search_symbols(
                str(query.arguments.get("query", "")),
                limit=int(query.arguments.get("limit", 20)),
            )
        elif query.method == "get_impact_radius":
            result = await context.codegraph.get_impact_radius(
                str(query.arguments["symbol"])
            )
        else:
            framework = query.arguments.get("framework")
            result = await context.codegraph.get_framework_routes(
                framework=str(framework) if framework is not None else None
            )
        return StepResult(
            step_id=step_id,
            success=True,
            output={"result": jsonable(result)},
            duration_ms=max(1, int((perf_counter() - started) * 1000)),
        )

    def _aggregate(
        self,
        step_id: str,
        context: AgentContext,
    ) -> StepResult:
        return StepResult(
            step_id=step_id,
            success=all(result.success for result in context.previous_results.values()),
            output={
                "steps": [
                    result.model_dump(mode="json")
                    for result in context.previous_results.values()
                ],
                "successful_steps": sum(
                    1 for result in context.previous_results.values() if result.success
                ),
            },
            duration_ms=1,
        )
