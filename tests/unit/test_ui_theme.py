from __future__ import annotations

from ivycode.core.envelope import AgentName, ProviderName
from ivycode.ui.theme import (
    MODEL_THEMES,
    PALETTE,
    ROUTER_THEME,
    theme_for_agent,
    theme_for_provider,
)


def test_palette_matches_spec_tokens() -> None:
    assert PALETTE.bg_base == "#0B0D12"
    assert PALETTE.bg_elevated == "#11141B"
    assert PALETTE.text_primary == "#E6E6E6"
    assert PALETTE.text_dim == "#6B7280"
    assert PALETTE.text_muted == "#3A3F4A"
    assert PALETTE.accent_warm == "#E5A98C"
    assert PALETTE.accent_mint == "#7CFFB2"
    assert PALETTE.accent_violet == "#A78BFA"
    assert PALETTE.accent_cyan == "#8AB4F8"
    assert PALETTE.warn == "#FFB070"
    assert PALETTE.error == "#FF6B6B"


def test_model_themes_match_provider_identity() -> None:
    assert MODEL_THEMES[ProviderName.ANTHROPIC].glyph == "◆"
    assert MODEL_THEMES[ProviderName.ANTHROPIC].border == "#C97B5C"
    assert MODEL_THEMES[ProviderName.OPENAI].glyph == "▲"
    assert MODEL_THEMES[ProviderName.OPENAI].border == "#10A37F"
    assert MODEL_THEMES[ProviderName.GOOGLE].glyph == "●"
    assert MODEL_THEMES[ProviderName.GOOGLE].border == "#8AB4F8"


def test_theme_lookup_uses_provider_and_agent_fallbacks() -> None:
    assert theme_for_provider(ProviderName.OPENAI) == MODEL_THEMES[ProviderName.OPENAI]
    assert theme_for_provider("custom").glyph == "■"
    assert theme_for_agent(AgentName.ROUTER) == ROUTER_THEME
    assert theme_for_agent(AgentName.TESTER).glyph == "✧"
