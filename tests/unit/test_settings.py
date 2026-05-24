from __future__ import annotations

from pathlib import Path

import pytest

from ivycode.core.envelope import ProviderName
from ivycode.core.settings import Settings


def test_settings_have_stage_one_defaults_without_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "IVYCODE_ANTHROPIC_API_KEY",
        "IVYCODE_OPENAI_API_KEY",
        "IVYCODE_GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.anthropic_api_key is None
    assert settings.openai_api_key is None
    assert settings.google_api_key is None
    assert settings.default_router_model.provider is ProviderName.ANTHROPIC
    assert settings.default_router_model.model_id == "claude-opus-4-7"
    assert settings.active_panel_providers == [settings.default_router_model]
    assert settings.max_concurrent_providers == 4
    assert settings.request_timeout_s == 120


def test_settings_paths_default_to_ivycode_home() -> None:
    settings = Settings()

    assert settings.cache_dir == Path.home() / ".ivycode" / "cache"
    assert settings.history_dir == Path.home() / ".ivycode" / "history"


def test_settings_reads_ivycode_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IVYCODE_OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("IVYCODE_MAX_CONCURRENT_PROVIDERS", "2")

    settings = Settings()

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test"
    assert settings.max_concurrent_providers == 2
