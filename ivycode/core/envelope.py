from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)


class IvyBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ProviderName(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class AgentName(StrEnum):
    ROUTER = "router"
    ARCHITECT = "architect"
    REFACTORER = "refactorer"
    TESTER = "tester"
    DOCUMENTER = "documenter"


class ModelRef(IvyBaseModel):
    provider: ProviderName
    model_id: str
    display_name: str


class UsageMetrics(IvyBaseModel):
    input_tokens: PositiveInt
    output_tokens: PositiveInt
    cached_input_tokens: NonNegativeInt = 0
    cost_usd: NonNegativeFloat
    latency_ms: PositiveInt


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class CallerMeta(IvyBaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    agent: AgentName
    model: ModelRef
    initiated_at: datetime = Field(default_factory=utc_now)
    tool_name: str | None = None

    @field_validator("initiated_at")
    @classmethod
    def _initiated_at_must_be_utc_aware(cls, value: datetime) -> datetime:
        return ensure_utc_aware(value)


class ToolCall(IvyBaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(IvyBaseModel):
    tool_call_id: str
    success: bool
    payload: dict[str, Any] | str
    error: str | None = None


class Message(IvyBaseModel):
    id: UUID = Field(default_factory=uuid4)
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_result: ToolResult | None = None
    meta: CallerMeta
    usage: UsageMetrics | None = None


class StreamEvent(IvyBaseModel):
    kind: Literal[
        "delta",
        "tool_call_start",
        "tool_call_args_delta",
        "tool_call_end",
        "stop",
        "error",
    ]
    text_delta: str | None = None
    tool_call: ToolCall | None = None
    args_delta: str | None = None
    meta: CallerMeta
    final_usage: UsageMetrics | None = None
    error_message: str | None = None


class StepKind(StrEnum):
    GRAPH_QUERY = "graph_query"
    SUBAGENT = "subagent"
    PARALLEL_COMPARE = "parallel_compare"
    AGGREGATE = "aggregate"


class GraphQuery(IvyBaseModel):
    method: Literal["search_symbols", "get_impact_radius", "get_framework_routes"]
    arguments: dict[str, str | int]


class SubAgentDirective(IvyBaseModel):
    agent: AgentName
    instructions: Annotated[str, Field(min_length=20)]
    inputs: dict[str, Any]
    allowed_skills: list[str] = Field(default_factory=list)
    token_budget: PositiveInt = 8000
    expected_output_schema: dict[str, Any] | None = None


class ParallelCompareDirective(IvyBaseModel):
    providers: list[ModelRef] = Field(min_length=2, max_length=4)
    prompt_template: str
    rubric: str


class PlanStep(IvyBaseModel):
    id: str = Field(pattern=r"^step_\d{2}$")
    kind: StepKind
    rationale: Annotated[str, Field(min_length=10, max_length=400)]
    depends_on: list[str] = Field(default_factory=list)
    graph_query: GraphQuery | None = None
    subagent: SubAgentDirective | None = None
    parallel_compare: ParallelCompareDirective | None = None
    timeout_s: PositiveInt = 60

    @model_validator(mode="after")
    def _payload_must_match_kind(self) -> PlanStep:
        payloads = {
            StepKind.GRAPH_QUERY: self.graph_query,
            StepKind.SUBAGENT: self.subagent,
            StepKind.PARALLEL_COMPARE: self.parallel_compare,
        }
        populated = [payload for payload in payloads.values() if payload is not None]

        if self.kind is StepKind.AGGREGATE:
            if populated:
                raise ValueError("aggregate step must not carry a directive payload")
            return self

        if len(populated) != 1:
            raise ValueError("PlanStep must carry exactly one directive payload")
        if payloads[self.kind] is None:
            raise ValueError("PlanStep payload must match its kind")
        return self


class ExecutionPlan(IvyBaseModel):
    summary: Annotated[str, Field(min_length=20, max_length=600)]
    risk_level: Literal["low", "medium", "high"]
    estimated_total_tokens: PositiveInt
    steps: list[PlanStep] = Field(min_length=1, max_length=12)
    final_aggregator: AgentName | None = None


class StepResult(IvyBaseModel):
    step_id: str
    success: bool
    output: dict[str, Any] | str
    usage: UsageMetrics | None = None
    error: str | None = None
    duration_ms: PositiveInt


class SessionTranscript(IvyBaseModel):
    session_id: UUID
    started_at: datetime
    plan: ExecutionPlan
    step_results: list[StepResult]
    final_message: Message
    total_usage: UsageMetrics

    @field_validator("started_at")
    @classmethod
    def _started_at_must_be_utc_aware(cls, value: datetime) -> datetime:
        return ensure_utc_aware(value)


class SymbolBrief(IvyBaseModel):
    qualified_name: str
    kind: Literal["function", "class", "method", "route", "constant"]
    file_path: str
    line_start: PositiveInt
    line_end: PositiveInt
    signature: str
    docstring_summary: str | None = None
    callers_count: NonNegativeInt
    callees_count: NonNegativeInt


class ImpactReport(IvyBaseModel):
    target: SymbolBrief
    direct_callers: list[SymbolBrief] = Field(max_length=20)
    transitive_callers_count: NonNegativeInt
    affected_files: list[str]
    risk_score: NonNegativeFloat


class FrameworkRoute(IvyBaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "WS"]
    path: str
    handler: SymbolBrief
    framework: Literal["fastapi", "django", "flask", "express", "fastify", "rails"]


class GraphSnapshot(IvyBaseModel):
    project_root: str
    indexed_files_count: NonNegativeInt
    relevant_symbols: list[SymbolBrief] = Field(max_length=30)
    relevant_routes: list[FrameworkRoute] = Field(default_factory=list, max_length=20)
    estimated_tokens: PositiveInt
