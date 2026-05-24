from __future__ import annotations

from enum import StrEnum

from pydantic import (
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    model_validator,
)

from ivycode.core.envelope import IvyBaseModel


class WireProtocol(StrEnum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GOOGLE_GENERATE_CONTENT = "google_generate_content"


class AuthKind(StrEnum):
    NONE = "none"
    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    GOOGLE_KEY_QUERY = "google_key_query"
    OAUTH_PKCE = "oauth_pkce"


class VendorName(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LITELLM = "litellm"
    CUSTOM = "custom"


class TransportConfig(IvyBaseModel):
    base_url: HttpUrl
    auth_kind: AuthKind = AuthKind.NONE
    api_key: SecretStr | None = None
    api_key_header: str | None = None
    extra_headers: dict[str, SecretStr] = Field(default_factory=dict)
    extra_cookies: dict[str, SecretStr] = Field(default_factory=dict)
    timeout_s: PositiveFloat = 120.0
    max_connections: PositiveInt = 32
    max_keepalive: PositiveInt = 16
    verify_tls: bool = True

    @model_validator(mode="after")
    def _validate_auth_and_tls(self) -> TransportConfig:
        if (
            self.auth_kind in {AuthKind.BEARER, AuthKind.API_KEY_HEADER}
            and self.api_key is None
        ):
            raise ValueError(f"api_key required for auth_kind={self.auth_kind}")
        if self.auth_kind is AuthKind.API_KEY_HEADER and not self.api_key_header:
            raise ValueError(
                "api_key_header (the header name) required when "
                "auth_kind=api_key_header"
            )
        if not self.verify_tls and not self._is_loopback_url():
            raise ValueError(
                "verify_tls=False is allowed only for localhost, 127.0.0.1, "
                "0.0.0.0, or ::1"
            )
        return self

    def _is_loopback_url(self) -> bool:
        host = self.base_url.host or ""
        return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


class PricingPolicy(IvyBaseModel):
    input_per_million_usd: PositiveFloat
    output_per_million_usd: PositiveFloat


class ProviderCapabilities(IvyBaseModel):
    supports_tools: bool = True
    supports_structured_output: bool = True
    supports_streaming: bool = True
    supports_prompt_cache: bool = False
    context_window: PositiveInt = 128_000


class ProviderProfile(IvyBaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,31}$")
    vendor: VendorName
    wire_protocol: WireProtocol
    model_id: str
    display_name: str
    pricing: PricingPolicy | None = None
    transport: TransportConfig
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
