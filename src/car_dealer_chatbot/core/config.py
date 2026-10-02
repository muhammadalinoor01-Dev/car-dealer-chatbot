"""Application configuration and secrets management.

All configuration is centralised here and loaded from environment variables or a
local ``.env`` file via :mod:`pydantic_settings`. Secrets (the OpenAI API key)
are therefore never hard-coded and never committed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Directory that ships the bundled sample CSV data.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are read (in priority order) from constructor arguments, environment
    variables, then a ``.env`` file. Unknown environment variables are ignored so
    the app coexists cleanly with other tools' configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openrouter_api_key: SecretStr = Field(
        ...,
        description="OpenRouter API key (https://openrouter.ai/keys).",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL (OpenAI-compatible endpoint).",
    )
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini",
        description="OpenRouter model id (must support tool calling), "
        "e.g. 'openai/gpt-4o-mini' or 'anthropic/claude-3.5-sonnet'.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the model.",
    )
    log_level: str = Field(
        default="INFO",
        description="Root logging level (DEBUG/INFO/WARNING/ERROR).",
    )
    cars_csv_path: Path = Field(
        default=_DATA_DIR / "cars.csv",
        description="Path to the cars CSV file.",
    )
    dealers_csv_path: Path = Field(
        default=_DATA_DIR / "dealers.csv",
        description="Path to the dealers CSV file.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Caching guarantees the ``.env`` file and environment are parsed once per
    process, and gives every layer a single shared configuration object.

    Returns:
        The application settings.

    Raises:
        pydantic.ValidationError: If required settings (e.g. the API key) are
            missing or invalid. Callers translate this into a friendly message.
    """
    return Settings()
