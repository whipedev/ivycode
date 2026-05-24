# Provider Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first provider transport foundation for ivycode.

**Architecture:** Define provider profile/config contracts, an abstract provider interface, codec registry, OpenAI-compatible chat codec, HTTP provider, and provider factory with one `httpx.AsyncClient` per profile.

**Tech Stack:** Python 3.11+, Pydantic v2, HTTPX, pytest, ruff, mypy.

---

### Task 1: Provider Profile Contracts

**Files:**
- Create: `tests/unit/test_provider_profile.py`
- Create: `ivycode/providers/profile.py`
- Create: `ivycode/providers/__init__.py`

- [ ] **Step 1: Write failing tests**

Tests cover transport auth validation, TLS validation, provider id validation,
strict extra-field rejection, and default capabilities.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_provider_profile.py -q`
Expected: FAIL because `ivycode.providers.profile` does not exist.

- [ ] **Step 3: Implement profile contracts**

Create `WireProtocol`, `AuthKind`, `TransportConfig`,
`ProviderCapabilities`, `PricingPolicy`, and `ProviderProfile`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_provider_profile.py -q`
Expected: PASS.

### Task 2: Provider Base and Codec Registry

**Files:**
- Create: `tests/unit/test_provider_base.py`
- Create: `ivycode/providers/base.py`
- Create: `ivycode/providers/codecs/__init__.py`
- Create: `ivycode/providers/codecs/base.py`

- [ ] **Step 1: Write failing tests**

Tests cover abstract provider behavior, request validation, codec registration,
and duplicate codec rejection.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_provider_base.py -q`
Expected: FAIL because provider base modules do not exist.

- [ ] **Step 3: Implement base contracts**

Create `ToolSchema`, `ProviderRequest`, `LLMProvider`, `WireCodec`,
`register_codec`, and `load_registered_codecs`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_provider_base.py -q`
Expected: PASS.

### Task 3: OpenAI Chat Codec

**Files:**
- Create: `tests/unit/test_openai_chat_codec.py`
- Create: `ivycode/providers/codecs/openai_chat.py`

- [ ] **Step 1: Write failing tests**

Tests cover OpenAI-compatible body construction, `model_id="auto"` passthrough,
JSON schema response format, SSE delta decoding, and gateway-style error chunks.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_openai_chat_codec.py -q`
Expected: FAIL because `OpenAIChatCodec` does not exist.

- [ ] **Step 3: Implement codec**

Create `OpenAIChatCodec` and register it for `WireProtocol.OPENAI_CHAT`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_openai_chat_codec.py -q`
Expected: PASS.

### Task 4: HTTP Provider and Factory

**Files:**
- Create: `tests/unit/test_http_provider.py`
- Modify: `pyproject.toml`
- Modify: `ivycode/core/settings.py`
- Create: `ivycode/providers/http_provider.py`
- Create: `ivycode/providers/factory.py`

- [ ] **Step 1: Write failing tests**

Tests cover `HttpProvider.stream()`, `complete_json()`, factory provider lookup,
and one client reused per provider id.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_http_provider.py -q`
Expected: FAIL because HTTP provider and factory modules do not exist.

- [ ] **Step 3: Add HTTPX dependency**

Add `httpx[http2]` to project dependencies and install the project into the
local virtual environment.

- [ ] **Step 4: Implement HTTP provider and factory**

Create provider streaming over `httpx.AsyncClient.stream()` and a factory that
builds clients with auth headers, cookies, timeouts, limits, and HTTP/2.

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_http_provider.py -q`
Expected: PASS.

### Task 5: Version and Verification

- [ ] **Step 1: Bump version**

Set `pyproject.toml` and `ivycode.__version__` to `0.3.0`. Update CLI stage
boundary to `v0.3.0-provider-foundation`.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy ivycode
python -m ivycode doctor
```

Expected: all commands exit with code 0.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add pyproject.toml docs ivycode tests
git commit -m "feat: add provider foundation"
git push
```

Expected: commit appears on `origin/main`.
