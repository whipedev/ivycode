from __future__ import annotations

from collections.abc import AsyncIterator
from typing import ClassVar

import pytest
from pydantic import ValidationError

from ivycode.core.envelope import CallerMeta, Message, ModelRef, ProviderName, Role
from ivycode.providers.base import LLMProvider, ProviderRequest
from ivycode.providers.codecs.base import (
    CodecAlreadyRegisteredError,
    WireCodec,
    load_registered_codecs,
    register_codec,
)
from ivycode.providers.profile import ProviderProfile, TransportConfig, WireProtocol


def test_provider_request_validates_generation_limits() -> None:
    model = ModelRef(
        provider=ProviderName.OPENAI,
        model_id="gpt-5.5-xhigh",
        display_name="GPT-5.5 xhigh",
    )
    meta = CallerMeta(agent="router", model=model)

    request = ProviderRequest(
        model="gpt-5.5-xhigh",
        system="You are Router.",
        messages=[Message(role=Role.USER, content="Plan.", meta=meta)],
        max_tokens=128,
        temperature=0.2,
    )

    assert request.messages[0].role is Role.USER

    with pytest.raises(ValidationError):
        ProviderRequest(
            model="gpt",
            system="system",
            messages=[],
            max_tokens=0,
            temperature=0.2,
        )

    with pytest.raises(ValidationError):
        ProviderRequest(
            model="gpt",
            system="system",
            messages=[Message(role=Role.USER, content="Plan.", meta=meta)],
            max_tokens=10,
            temperature=3.0,
        )


def test_llm_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_codec_registry_registers_protocol_once() -> None:
    class TestCodec:
        wire_protocol: ClassVar[WireProtocol] = WireProtocol.OPENAI_RESPONSES

        def build_request(
            self,
            req: ProviderRequest,
            profile: ProviderProfile,
        ) -> tuple[str, dict[str, object]]:
            return "responses", {"model": req.model, "profile": profile.id}

        async def decode_stream(
            self,
            response: object,
            meta: CallerMeta,
        ) -> AsyncIterator[object]:
            if False:
                yield response

    registered = register_codec(WireProtocol.OPENAI_RESPONSES)(TestCodec)

    assert registered is TestCodec
    assert WireProtocol.OPENAI_RESPONSES in load_registered_codecs()

    with pytest.raises(CodecAlreadyRegisteredError):
        register_codec(WireProtocol.OPENAI_RESPONSES)(TestCodec)


def test_wire_codec_protocol_accepts_registered_codec() -> None:
    codecs = load_registered_codecs()
    codec = codecs[WireProtocol.OPENAI_RESPONSES]

    assert isinstance(codec, WireCodec)

    profile = ProviderProfile(
        id="test_openai",
        vendor="openai",
        wire_protocol=WireProtocol.OPENAI_RESPONSES,
        model_id="gpt-test",
        display_name="GPT Test",
        transport=TransportConfig(base_url="https://api.openai.com/v1/"),
    )
    request = ProviderRequest(
        model="gpt-test",
        system="system",
        messages=[],
    )

    assert codec.build_request(request, profile)[0] == "responses"
