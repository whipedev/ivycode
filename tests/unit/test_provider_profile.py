from __future__ import annotations

import pytest
from pydantic import ValidationError

from ivycode.providers.profile import (
    AuthKind,
    ProviderCapabilities,
    ProviderProfile,
    TransportConfig,
    VendorName,
    WireProtocol,
)


def test_transport_config_allows_localhost_without_tls() -> None:
    transport = TransportConfig(
        base_url="http://localhost:11434/v1/",
        auth_kind=AuthKind.NONE,
        verify_tls=False,
    )

    assert str(transport.base_url) == "http://localhost:11434/v1/"
    assert transport.verify_tls is False


def test_transport_config_rejects_remote_without_tls() -> None:
    with pytest.raises(ValidationError, match="verify_tls=False"):
        TransportConfig(
            base_url="https://api.example.com/v1/",
            auth_kind=AuthKind.NONE,
            verify_tls=False,
        )


def test_transport_config_requires_api_key_for_auth() -> None:
    with pytest.raises(ValidationError, match="api_key required"):
        TransportConfig(
            base_url="https://api.openai.com/v1/",
            auth_kind=AuthKind.BEARER,
        )

    with pytest.raises(ValidationError, match="api_key_header"):
        TransportConfig(
            base_url="https://api.anthropic.com/",
            auth_kind=AuthKind.API_KEY_HEADER,
            api_key="secret",
        )


def test_provider_profile_is_strict_and_validates_id() -> None:
    transport = TransportConfig(base_url="http://localhost:11434/v1/")
    profile = ProviderProfile(
        id="local_llama",
        vendor=VendorName.OLLAMA,
        wire_protocol=WireProtocol.OPENAI_CHAT,
        model_id="llama3.1:8b",
        display_name="Llama 3.1 8B",
        transport=transport,
    )

    assert profile.capabilities == ProviderCapabilities()
    assert profile.capabilities.context_window == 128_000

    with pytest.raises(ValidationError):
        ProviderProfile.model_validate(
            {
                "id": "Bad ID",
                "vendor": "ollama",
                "wire_protocol": "openai_chat",
                "model_id": "llama3.1:8b",
                "display_name": "Llama",
                "transport": {"base_url": "http://localhost:11434/v1/"},
            }
        )

    with pytest.raises(ValidationError):
        ProviderProfile.model_validate(
            {
                "id": "local_llama",
                "vendor": "ollama",
                "wire_protocol": "openai_chat",
                "model_id": "llama3.1:8b",
                "display_name": "Llama",
                "transport": {"base_url": "http://localhost:11434/v1/"},
                "extra": "rejected",
            }
        )
