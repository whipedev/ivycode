from __future__ import annotations

import asyncio

import httpx
import pytest

from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    Message,
    ModelRef,
    ProviderName,
    Role,
)
from ivycode.core.settings import Settings
from ivycode.providers.factory import ProviderFactory, ProviderNotConfiguredError
from ivycode.providers.profile import (
    AuthKind,
    ProviderProfile,
    TransportConfig,
    VendorName,
    WireProtocol,
)


def _meta() -> CallerMeta:
    model = ModelRef(
        provider=ProviderName.OPENAI,
        model_id="gpt-5.5-xhigh",
        display_name="GPT-5.5 xhigh",
    )
    return CallerMeta(agent=AgentName.ROUTER, model=model)


def _settings() -> Settings:
    return Settings(
        providers={
            "gateway": ProviderProfile(
                id="gateway",
                vendor=VendorName.CUSTOM,
                wire_protocol=WireProtocol.OPENAI_CHAT,
                model_id="auto",
                display_name="Local Gateway",
                transport=TransportConfig(
                    base_url="http://127.0.0.1:7878/v1/",
                    auth_kind=AuthKind.NONE,
                    verify_tls=False,
                ),
            )
        }
    )


def test_http_provider_streams_normalized_events_from_mock_transport() -> None:
    async def run() -> list[str | None]:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/chat/completions"
            assert request.headers["x-correlation-id"]
            return httpx.Response(
                200,
                content=(
                    'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    "data: [DONE]\n\n"
                ),
                headers={"content-type": "text/event-stream"},
            )

        factory = ProviderFactory(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        provider = factory.create("gateway")
        events = [
            ev
            async for ev in provider.stream(
                system="system",
                messages=[Message(role=Role.USER, content="hi", meta=_meta())],
                meta=_meta(),
            )
        ]
        await factory.aclose()
        return [ev.text_delta if ev.kind == "delta" else ev.kind for ev in events]

    assert asyncio.run(run()) == ["hello", "stop"]


def test_http_provider_complete_json_collects_delta_text() -> None:
    async def run() -> str:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=(
                    'data: {"choices":[{"delta":{"content":"{\\"ok\\":"}}]}\n\n'
                    'data: {"choices":[{"delta":{"content":"true}"}}]}\n\n'
                    "data: [DONE]\n\n"
                ),
                headers={"content-type": "text/event-stream"},
            )

        factory = ProviderFactory(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        provider = factory.create("gateway")
        raw = await provider.complete_json(
            system="system",
            user="return json",
            response_schema={"type": "object"},
            meta=_meta(),
        )
        await factory.aclose()
        return raw

    assert asyncio.run(run()) == '{"ok":true}'


def test_provider_factory_reuses_client_and_rejects_unknown_provider() -> None:
    factory = ProviderFactory(
        _settings(),
        transport=httpx.MockTransport(lambda _: None),
    )

    first = factory.create("gateway")
    second = factory.create("gateway")

    assert first.client is second.client

    with pytest.raises(ProviderNotConfiguredError):
        factory.create("missing")

    asyncio.run(factory.aclose())
