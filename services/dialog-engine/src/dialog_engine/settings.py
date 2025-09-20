from __future__ import annotations

"""Runtime configuration helpers for dialog-engine."""

import os
from dataclasses import dataclass

_BOOL_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _BOOL_TRUTHY


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):  # defensive cast
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str | None
    organization: str | None
    base_url: str | None


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    model: str
    temperature: float
    max_tokens: int
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    timeout: float
    retry_limit: int
    retry_backoff_seconds: float


@dataclass(frozen=True)
class ShortTermMemorySettings:
    enabled: bool
    db_path: str
    context_turns: int


@dataclass(frozen=True)
class LTMInlineSettings:
    enabled: bool
    base_url: str | None
    retrieve_path: str
    timeout: float
    max_snippets: int


@dataclass(frozen=True)
class Settings:
    openai: OpenAISettings
    llm: LLMSettings
    short_term: ShortTermMemorySettings
    ltm_inline: LTMInlineSettings


def load_settings() -> Settings:
    """Load settings from environment variables with sensible defaults."""

    llm_settings = LLMSettings(
        enabled=_env_bool("ENABLE_REAL_LLM", False),
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=_env_float("LLM_TEMPERATURE", 0.7),
        max_tokens=_env_int("LLM_MAX_TOKENS", 1024),
        top_p=_env_float("LLM_TOP_P", 1.0),
        frequency_penalty=_env_float("LLM_FREQUENCY_PENALTY", 0.0),
        presence_penalty=_env_float("LLM_PRESENCE_PENALTY", 0.0),
        timeout=_env_float("LLM_REQUEST_TIMEOUT", 30.0),
        retry_limit=_env_int("LLM_RETRY_LIMIT", 2),
        retry_backoff_seconds=_env_float("LLM_RETRY_BACKOFF_SECONDS", 0.5),
    )

    openai_settings = OpenAISettings(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG_ID"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    short_term_settings = ShortTermMemorySettings(
        enabled=_env_bool("ENABLE_SHORT_TERM_MEMORY", True),
        db_path=os.getenv("STM_DB_PATH", "/app/data/dialog_memory.sqlite"),
        context_turns=_env_int("STM_CONTEXT_TURNS", 20),
    )

    ltm_inline_settings = LTMInlineSettings(
        enabled=_env_bool("ENABLE_LTM_INLINE", False),
        base_url=os.getenv("LTM_BASE_URL"),
        retrieve_path=os.getenv("LTM_RETRIEVE_PATH", "/v1/memory/retrieve"),
        timeout=_env_float("LTM_RETRIEVE_TIMEOUT", 3.0),
        max_snippets=_env_int("LTM_MAX_SNIPPETS", 5),
    )

    return Settings(
        openai=openai_settings,
        llm=llm_settings,
        short_term=short_term_settings,
        ltm_inline=ltm_inline_settings,
    )


settings = load_settings()

__all__ = [
    "Settings",
    "LLMSettings",
    "OpenAISettings",
    "ShortTermMemorySettings",
    "LTMInlineSettings",
    "settings",
    "load_settings",
]
