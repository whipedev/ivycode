from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import Field

from ivycode.agents.base import (
    AgentContext,
    JsonObject,
    JsonSchema,
    SubAgent,
    validate_json_object_schema,
)
from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    IvyBaseModel,
    ModelRef,
    StepResult,
    SubAgentDirective,
)
from ivycode.core.settings import DEFAULT_ROUTER_MODEL
from ivycode.providers.base import LLMProvider


class ArchitectReport(IvyBaseModel):
    summary: str = Field(min_length=20)
    decisions: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


ARCHITECT_REPORT_SCHEMA = ArchitectReport.model_json_schema()


class ArchitectSubAgent(SubAgent):
    name = AgentName.ARCHITECT
    description = "Architecture planning subagent for grounded implementation plans."

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        model: ModelRef = DEFAULT_ROUTER_MODEL,
        prompt_path: Path | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._prompt_path = prompt_path or (
            Path(__file__).resolve().parents[1] / "prompts" / "architect.md"
        )

    async def execute(
        self,
        *,
        step_id: str,
        directive: SubAgentDirective,
        context: AgentContext,
    ) -> StepResult:
        started = perf_counter()
        schema = directive.expected_output_schema or ARCHITECT_REPORT_SCHEMA
        payload = (
            await self._provider_payload(directive, schema)
            if self._provider is not None
            else self._fallback_payload(directive, context)
        )
        validated = validate_json_object_schema(payload, schema)
        return StepResult(
            step_id=step_id,
            success=True,
            output=validated,
            duration_ms=max(1, int((perf_counter() - started) * 1000)),
        )

    async def _provider_payload(
        self,
        directive: SubAgentDirective,
        schema: JsonSchema,
    ) -> JsonObject:
        assert self._provider is not None
        raw = await self._provider.complete_json(
            system=self._prompt_path.read_text(encoding="utf-8"),
            user=json.dumps(directive.inputs, indent=2),
            response_schema=schema,
            meta=CallerMeta(agent=AgentName.ARCHITECT, model=self._model),
        )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("architect provider returned non-object JSON")
        return payload

    def _fallback_payload(
        self,
        directive: SubAgentDirective,
        context: AgentContext,
    ) -> JsonObject:
        files = _file_refs_from_inputs(directive.inputs)
        task = str(directive.inputs.get("user_task", "the requested change"))
        report = ArchitectReport(
            summary=f"Architecture review for {task} grounded in CodeGraph context.",
            decisions=[
                "Start from CodeGraph references before reading source ranges.",
                "Keep implementation scoped to the files identified by the plan.",
            ],
            files=files,
            risks=[] if files else ["No matching CodeGraph symbols were found."],
            next_steps=[
                "Review the graph query results.",
                "Read only explicit file ranges before editing.",
            ],
        )
        _ = context
        return report.model_dump(mode="json")


def _file_refs_from_inputs(inputs: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    snapshot = inputs.get("graph_snapshot")
    if isinstance(snapshot, dict):
        symbols = snapshot.get("relevant_symbols", [])
        if isinstance(symbols, list):
            for symbol in symbols:
                if not isinstance(symbol, dict):
                    continue
                file_path = symbol.get("file_path")
                line_start = symbol.get("line_start")
                line_end = symbol.get("line_end")
                if (
                    isinstance(file_path, str)
                    and isinstance(line_start, int)
                    and isinstance(line_end, int)
                ):
                    refs.append(f"{file_path}:{line_start}-{line_end}")
    return sorted(set(refs))
