from __future__ import annotations

from ivycode.core.envelope import AgentName, IvyBaseModel, ProviderName


class Palette(IvyBaseModel):
    bg_base: str
    bg_elevated: str
    text_primary: str
    text_dim: str
    text_muted: str
    accent_warm: str
    accent_mint: str
    accent_violet: str
    accent_cyan: str
    warn: str
    error: str


class ModelTheme(IvyBaseModel):
    glyph: str
    border: str
    accent: str


PALETTE = Palette(
    bg_base="#0B0D12",
    bg_elevated="#11141B",
    text_primary="#E6E6E6",
    text_dim="#6B7280",
    text_muted="#3A3F4A",
    accent_warm="#E5A98C",
    accent_mint="#7CFFB2",
    accent_violet="#A78BFA",
    accent_cyan="#8AB4F8",
    warn="#FFB070",
    error="#FF6B6B",
)

MODEL_THEMES: dict[ProviderName, ModelTheme] = {
    ProviderName.ANTHROPIC: ModelTheme(
        glyph="◆",
        border="#C97B5C",
        accent="#E5A98C",
    ),
    ProviderName.OPENAI: ModelTheme(
        glyph="▲",
        border="#10A37F",
        accent="#5BD3B0",
    ),
    ProviderName.GOOGLE: ModelTheme(
        glyph="●",
        border="#8AB4F8",
        accent="#C7D8FB",
    ),
}

ROUTER_THEME = ModelTheme(glyph="✦", border="#A78BFA", accent="#C7B6FF")
LOCAL_MODEL_THEME = ModelTheme(glyph="■", border="#94A3B8", accent="#CBD5E1")

SUBAGENT_THEMES: dict[AgentName, ModelTheme] = {
    AgentName.ROUTER: ROUTER_THEME,
    AgentName.ARCHITECT: ModelTheme(glyph="✧", border="#E5A98C", accent="#F3C7AE"),
    AgentName.REFACTORER: ModelTheme(glyph="✧", border="#7CFFB2", accent="#B4FFD0"),
    AgentName.TESTER: ModelTheme(glyph="✧", border="#8AB4F8", accent="#C7D8FB"),
    AgentName.DOCUMENTER: ModelTheme(glyph="✧", border="#A78BFA", accent="#D7C9FF"),
}


def theme_for_provider(provider: ProviderName | str) -> ModelTheme:
    if isinstance(provider, ProviderName):
        return MODEL_THEMES.get(provider, LOCAL_MODEL_THEME)
    try:
        parsed = ProviderName(provider)
    except ValueError:
        return LOCAL_MODEL_THEME
    return MODEL_THEMES.get(parsed, LOCAL_MODEL_THEME)


def theme_for_agent(agent: AgentName) -> ModelTheme:
    return SUBAGENT_THEMES[agent]
