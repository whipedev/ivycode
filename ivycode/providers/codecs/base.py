from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol, cast, runtime_checkable

from ivycode.core.envelope import CallerMeta, StreamEvent
from ivycode.providers.base import ProviderRequest
from ivycode.providers.profile import ProviderProfile, WireProtocol


class CodecAlreadyRegisteredError(RuntimeError):
    pass


@runtime_checkable
class StreamResponse(Protocol):
    def aiter_lines(self) -> AsyncIterator[str]:
        ...


@runtime_checkable
class WireCodec(Protocol):
    wire_protocol: WireProtocol

    def build_request(
        self,
        req: ProviderRequest,
        profile: ProviderProfile,
    ) -> tuple[str, dict[str, object]]:
        ...

    def decode_stream(
        self,
        response: StreamResponse,
        meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        ...


_CODEC_TYPES: dict[WireProtocol, type[Any]] = {}


def register_codec(protocol: WireProtocol) -> Callable[[type[Any]], type[Any]]:
    def decorator(codec_type: type[Any]) -> type[Any]:
        if protocol in _CODEC_TYPES:
            raise CodecAlreadyRegisteredError(
                f"codec already registered for {protocol.value}"
            )
        _CODEC_TYPES[protocol] = codec_type
        return codec_type

    return decorator


def load_registered_codecs() -> dict[WireProtocol, WireCodec]:
    return {
        protocol: cast(WireCodec, codec_type())
        for protocol, codec_type in _CODEC_TYPES.items()
    }
