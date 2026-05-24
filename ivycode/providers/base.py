from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any, ClassVar

from pydantic import Field, PositiveInt

from ivycode.core.envelope import (
    CallerMeta,
    IvyBaseModel,
    Message,
    ProviderName,
    StreamEvent,
)

ToolSchema = dict[str, Any]


class ProviderRequest(IvyBaseModel):
    model: str
    system: str
    messages: Sequence[Message] = Field(default_factory=list)
    tools: Sequence[ToolSchema] = Field(default_factory=list)
    response_schema: dict[str, Any] | None = None
    max_tokens: PositiveInt = 4096
    temperature: float = Field(default=0.2, ge=0, le=2)
    meta: CallerMeta | None = None


class LLMProvider(ABC):
    name: ClassVar[ProviderName | str]

    @abstractmethod
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

    @abstractmethod
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        meta: CallerMeta,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        raise NotImplementedError
