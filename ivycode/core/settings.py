from __future__ import annotations

from pathlib import Path

from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from ivycode.core.envelope import ModelRef, ProviderName

DEFAULT_ROUTER_MODEL = ModelRef(
    provider=ProviderName.ANTHROPIC,
    model_id="claude-opus-4-7",
    display_name="Claude Opus 4.7",
)

DEFAULT_CONFIG_PATH = Path.home() / ".ivycode" / "config.toml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IVYCODE_",
        env_file=".env",
        toml_file=DEFAULT_CONFIG_PATH,
    )

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    default_router_model: ModelRef = DEFAULT_ROUTER_MODEL
    active_panel_providers: list[ModelRef] = Field(
        default_factory=lambda: [DEFAULT_ROUTER_MODEL]
    )
    project_root: Path = Field(default_factory=Path.cwd)
    cache_dir: Path = Path.home() / ".ivycode" / "cache"
    history_dir: Path = Path.home() / ".ivycode" / "history"
    max_concurrent_providers: PositiveInt = 4
    request_timeout_s: PositiveInt = 120

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=DEFAULT_CONFIG_PATH),
            file_secret_settings,
        )
