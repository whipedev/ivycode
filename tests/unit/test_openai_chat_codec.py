from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    Message,
    ModelRef,
    ProviderName,
    Role,
)
from ivycode.providers.base import ProviderRequest
from ivycode.providers.codecs.openai_chat import OpenAIChatCodec
from ivycode.providers.profile import (
    ProviderProfile,
    TransportConfig,
    VendorName,
    WireProtocol,
)


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


def _meta() -> CallerMeta:
    model = ModelRef(
        provider=ProviderName.OPENAI,
        model_id="gpt-5.5-xhigh",
        display_name="GPT-5.5 xhigh",
    )
    return CallerMeta(agent=AgentName.ROUTER, model=model)


def _profile(model_id: str = "gpt-5.5-xhigh") -> ProviderProfile:
    return ProviderProfile(
        id="gpt",
        vendor=VendorName.OPENAI,
        wire_protocol=WireProtocol.OPENAI_CHAT,
        model_id=model_id,
        display_name="GPT",
        transport=TransportConfig(base_url="https://api.openai.com/v1/"),
    )


def test_openai_chat_codec_builds_streaming_request_body() -> None:
    meta = _meta()
    request = ProviderRequest(
        model="gpt-5.5-xhigh",
        system="You are Router.",
        messages=[Message(role=Role.USER, content="Say hi.", meta=meta)],
        tools=[{"type": "function", "function": {"name": "search_symbols"}}],
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        max_tokens=512,
        temperature=0.1,
    )

    path, body = OpenAIChatCodec().build_request(request, _profile())

    assert path == "chat/completions"
    assert body["model"] == "gpt-5.5-xhigh"
    assert body["stream"] is True
    assert body["messages"] == [
        {"role": "system", "content": "You are Router."},
        {"role": "user", "content": "Say hi."},
    ]
    assert body["tools"] == request.tools
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "schema": request.response_schema,
            "strict": True,
        },
    }


def test_openai_chat_codec_uses_request_model_when_profile_is_auto() -> None:
    request = ProviderRequest(model="llama3.1:8b", system="", messages=[])
    profile = _profile(model_id="auto")

    _, body = OpenAIChatCodec().build_request(request, profile)

    assert body["model"] == "llama3.1:8b"


def test_openai_chat_codec_decodes_delta_and_stop_events() -> None:
    async def run() -> list[str | None]:
        response = FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"hel"}}]}',
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                "data: [DONE]",
            ]
        )
        events = [
            ev async for ev in OpenAIChatCodec().decode_stream(response, _meta())
        ]
        return [ev.text_delta if ev.kind == "delta" else ev.kind for ev in events]

    assert asyncio.run(run()) == ["hel", "lo", "stop"]


def test_openai_chat_codec_decodes_gateway_error_chunk() -> None:
    async def run() -> tuple[str, str | None]:
        response = FakeStreamResponse(
            [
                'data: {"error":{"code":"queue_full","message":"retry later"}}',
                "data: [DONE]",
            ]
        )
        events = [
            ev async for ev in OpenAIChatCodec().decode_stream(response, _meta())
        ]
        return events[0].kind, events[0].error_message

    assert asyncio.run(run()) == ("error", "retry later")
