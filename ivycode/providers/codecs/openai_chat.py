from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

from ivycode.core.envelope import CallerMeta, Message, Role, StreamEvent
from ivycode.providers.base import ProviderRequest
from ivycode.providers.codecs.base import StreamResponse, register_codec
from ivycode.providers.profile import ProviderProfile, WireProtocol


@register_codec(WireProtocol.OPENAI_CHAT)
class OpenAIChatCodec:
    wire_protocol = WireProtocol.OPENAI_CHAT

    def build_request(
        self,
        req: ProviderRequest,
        profile: ProviderProfile,
    ) -> tuple[str, dict[str, object]]:
        body: dict[str, object] = {
            "model": profile.model_id if profile.model_id != "auto" else req.model,
            "messages": self._messages(req.system, req.messages),
            "stream": True,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.tools:
            body["tools"] = list(req.tools)
        if req.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": req.response_schema,
                    "strict": True,
                },
            }
        return "chat/completions", body

    async def decode_stream(
        self,
        response: StreamResponse,
        meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            raw = line.removeprefix("data: ").strip()
            if raw == "[DONE]":
                yield StreamEvent(kind="stop", meta=meta)
                return

            chunk = json.loads(raw)
            if (error := chunk.get("error")) is not None:
                message = (
                    error.get("message", "upstream error")
                    if isinstance(error, dict)
                    else "upstream error"
                )
                yield StreamEvent(kind="error", error_message=message, meta=meta)
                yield StreamEvent(kind="stop", meta=meta)
                return

            choices = chunk.get("choices") or []
            if not choices:
                continue
            first = choices[0]
            delta = first.get("delta") or {}
            if (text := delta.get("content")) and isinstance(text, str):
                yield StreamEvent(kind="delta", text_delta=text, meta=meta)
            if first.get("finish_reason"):
                yield StreamEvent(kind="stop", meta=meta)
                return

    @staticmethod
    def _messages(system: str, messages: Sequence[Message]) -> list[dict[str, object]]:
        rendered: list[dict[str, object]] = []
        if system:
            rendered.append({"role": Role.SYSTEM.value, "content": system})
        for message in messages:
            rendered.append(
                {
                    "role": message.role.value,
                    "content": message.content or "",
                }
            )
        return rendered
