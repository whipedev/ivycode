# Ivycode Provider Foundation Design

## Scope

This stage implements the provider transport foundation for `v0.3.0` from
`PROMPT_SPEC.md` sections 6 and 18:

- `providers/base.py`
- `providers/profile.py`
- `providers/codecs/base.py`
- `providers/codecs/openai_chat.py`
- `providers/http_provider.py`
- `providers/factory.py`

This stage implements a real HTTP provider shell and OpenAI-compatible chat
wire codec because section 18 states that Ollama, vLLM, LM Studio, LiteLLM, and
local mock servers can share `wire_protocol = "openai_chat"`.

## Non-Scope

This stage does not implement Anthropic Messages, OpenAI Responses, or Google
Generate Content vendor codecs. It does not call live cloud APIs. Those follow
after the shared transport contract is tested.

## Architecture

`providers.profile` owns immutable Pydantic configuration for transports and
provider profiles. It validates auth requirements and prevents disabling TLS
outside loopback hosts.

`providers.base` owns the `LLMProvider` ABC and the `ProviderRequest` contract.
It keeps agents independent from HTTP, SDKs, and vendor-specific payloads.

`providers.codecs` owns protocol-specific body construction and stream decoding.
The codec registry maps `WireProtocol` values to codec instances.

`providers.http_provider` composes one `ProviderProfile`, one `httpx.AsyncClient`,
and one `WireCodec`. It implements `stream()` and `complete_json()` by returning
normalized `StreamEvent` objects.

`providers.factory` owns one `AsyncClient` per provider id and builds auth
headers once. It never mutates shared client headers after construction.

## Testing

Tests verify:

- provider profile validation
- strict/frozen Pydantic behavior
- OpenAI-compatible request body construction
- OpenAI-compatible SSE decoding into `StreamEvent`
- HTTP provider streaming through `httpx.MockTransport`
- factory client reuse and unknown-provider errors

## Verification

Before commit:

- `python -m pytest -q`
- `python -m ruff check .`
- `python -m mypy ivycode`
- `python -m ivycode doctor`
