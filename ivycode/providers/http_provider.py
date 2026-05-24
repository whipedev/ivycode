from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from math import ceil
from typing import Any

import httpx

from ivycode.core.envelope import CallerMeta, Message, Role, StreamEvent
from ivycode.providers.base import LLMProvider, ProviderRequest, ToolSchema
from ivycode.providers.codecs.base import WireCodec
from ivycode.providers.profile import ProviderProfile


class ProviderStreamError(RuntimeError):
    pass


class HttpProvider(LLMProvider):
    name = "http"

    def __init__(
        self,
        profile: ProviderProfile,
        client: httpx.AsyncClient,
        codec: WireCodec,
    ) -> None:
        self._profile = profile
        self._client = client
        self._codec = codec

    @property
    def profile(self) -> ProviderProfile:
        return self._profile

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def stream(
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
        request = ProviderRequest(
            model=self._profile.model_id,
            system=system,
            messages=list(messages),
            tools=list(tools),
            response_schema=response_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            meta=meta,
        )
        path, body = self._codec.build_request(request, self._profile)
        headers = {"X-Correlation-Id": str(meta.trace_id)}

        async with self._client.stream(
            "POST",
            path,
            json=body,
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                yield StreamEvent(
                    kind="error",
                    error_message=await self._read_error(response),
                    meta=meta,
                )
                yield StreamEvent(kind="stop", meta=meta)
                return
            async for event in self._codec.decode_stream(response, meta):
                yield event

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        meta: CallerMeta,
    ) -> str:
        message = Message(role=Role.USER, content=user, meta=meta)
        chunks: list[str] = []
        async for event in self.stream(
            system=system,
            messages=[message],
            response_schema=response_schema,
            meta=meta,
        ):
            if event.kind == "delta" and event.text_delta:
                chunks.append(event.text_delta)
            elif event.kind == "error":
                raise ProviderStreamError(event.error_message or "provider error")
        return "".join(chunks)

    def estimate_tokens(self, text: str) -> int:
        return max(1, ceil(len(text) / 4))

    @staticmethod
    async def _read_error(response: httpx.Response) -> str:
        try:
            payload = await response.aread()
            parsed = json_loads(payload)
        except ValueError:
            return response.reason_phrase
        error = parsed.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        return response.reason_phrase


def json_loads(payload: bytes) -> dict[str, Any]:
    import json

    parsed = json.loads(payload)
    return parsed if isinstance(parsed, dict) else {}
