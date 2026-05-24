from __future__ import annotations

from collections.abc import Mapping

import httpx

from ivycode.core.settings import Settings
from ivycode.providers.codecs import load_registered_codecs
from ivycode.providers.codecs.base import WireCodec
from ivycode.providers.http_provider import HttpProvider
from ivycode.providers.profile import AuthKind, ProviderProfile, WireProtocol


class ProviderNotConfiguredError(KeyError):
    pass


class ProviderFactory:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        codecs: Mapping[WireProtocol, WireCodec] | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._codecs = dict(codecs or load_registered_codecs())

    def create(self, provider_id: str) -> HttpProvider:
        profile = self._settings.providers.get(provider_id)
        if profile is None:
            raise ProviderNotConfiguredError(provider_id)

        client = self._clients.get(provider_id)
        if client is None:
            client = self._build_client(profile)
            self._clients[provider_id] = client

        codec = self._codecs[profile.wire_protocol]
        return HttpProvider(profile, client, codec)

    def _build_client(self, profile: ProviderProfile) -> httpx.AsyncClient:
        cfg = profile.transport
        headers = {
            key: value.get_secret_value() for key, value in cfg.extra_headers.items()
        }
        cookies = {
            key: value.get_secret_value() for key, value in cfg.extra_cookies.items()
        }

        if cfg.auth_kind is AuthKind.BEARER and cfg.api_key is not None:
            headers["Authorization"] = f"Bearer {cfg.api_key.get_secret_value()}"
        elif cfg.auth_kind is AuthKind.API_KEY_HEADER and cfg.api_key is not None:
            assert cfg.api_key_header is not None
            headers[cfg.api_key_header] = cfg.api_key.get_secret_value()

        return httpx.AsyncClient(
            base_url=str(cfg.base_url),
            headers=headers,
            cookies=cookies,
            timeout=httpx.Timeout(cfg.timeout_s),
            limits=httpx.Limits(
                max_connections=cfg.max_connections,
                max_keepalive_connections=cfg.max_keepalive,
            ),
            verify=cfg.verify_tls,
            http2=True,
            transport=self._transport,
        )

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
