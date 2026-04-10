"""Tests for provider settings, URL normalization, and CLI formatting."""

from __future__ import annotations

import pytest

from nocode.config.settings import (
    DEFAULT_ANTHROPIC_BASE_URL,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_MOONSHOT_BASE_URL,
    DEFAULT_MOONSHOT_MODEL,
    NOCODE_LLM_ANTHROPIC,
    NOCODE_LLM_MOONSHOT,
    AnthropicConfig,
    MoonshotConfig,
    Settings,
    anthropic_base_url_mismatch_hint,
    is_kimi_coding_anthropic_base,
    is_moonshot_anthropic_messages_base,
    normalize_anthropic_base_url,
)
from nocode.config import settings as settings_module


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        (" https://api.anthropic.com/ ", "https://api.anthropic.com"),
        ("https://api.anthropic.com/v1", "https://api.anthropic.com"),
        ("https://api.anthropic.com/v1/", "https://api.anthropic.com"),
        ("https://api.moonshot.cn/anthropic", "https://api.moonshot.cn/anthropic/"),
        ("https://api.kimi.com/coding/", "https://api.kimi.com/coding/"),
    ],
)
def test_normalize_anthropic_base_url(raw: str | None, expected: str | None) -> None:
    assert normalize_anthropic_base_url(raw) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://api.moonshot.cn/anthropic", True),
        ("https://api.moonshot.ai/company/anthropic", True),
        ("https://api.moonshot.cn/v1", False),
        ("https://api.anthropic.com", False),
    ],
)
def test_is_moonshot_anthropic_messages_base(url: str, expected: bool) -> None:
    assert is_moonshot_anthropic_messages_base(url) is expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://api.kimi.com/coding", True),
        ("https://api.kimi.com/company/coding", True),
        ("https://api.kimi.com/v1", False),
        ("https://api.moonshot.cn/anthropic", False),
    ],
)
def test_is_kimi_coding_anthropic_base(url: str, expected: bool) -> None:
    assert is_kimi_coding_anthropic_base(url) is expected


def test_mismatch_hint_for_moonshot_host_without_anthropic_path() -> None:
    hint = anthropic_base_url_mismatch_hint("https://api.moonshot.cn/v1")

    assert hint is not None
    assert "Moonshot" in hint
    assert "ANTHROPIC_BASE_URL" in hint


def test_mismatch_hint_for_openai_compatible_gateway() -> None:
    hint = anthropic_base_url_mismatch_hint("https://api.openai.com/v1")

    assert hint is not None
    assert "OpenAI" in hint
    assert DEFAULT_ANTHROPIC_BASE_URL in hint


def test_mismatch_hint_is_none_for_valid_messages_endpoints() -> None:
    assert anthropic_base_url_mismatch_hint("https://api.anthropic.com") is None
    assert anthropic_base_url_mismatch_hint("https://api.moonshot.cn/anthropic") is None


def test_anthropic_config_auth_kwargs_prefers_api_key() -> None:
    config = AnthropicConfig(
        base_url=DEFAULT_ANTHROPIC_BASE_URL,
        model=DEFAULT_ANTHROPIC_MODEL,
        api_key="api-key",
        auth_token="auth-token",
    )

    assert config.auth_kwargs() == {"api_key": "api-key"}
    assert config.configured_credential() == "api-key"


def test_anthropic_config_auth_kwargs_falls_back_to_auth_token() -> None:
    config = AnthropicConfig(
        base_url=DEFAULT_ANTHROPIC_BASE_URL,
        model=DEFAULT_ANTHROPIC_MODEL,
        api_key=None,
        auth_token="auth-token",
    )

    assert config.auth_kwargs() == {"auth_token": "auth-token"}
    assert config.configured_credential() == "auth-token"


def test_anthropic_config_auth_kwargs_can_be_empty() -> None:
    config = AnthropicConfig(
        base_url=DEFAULT_ANTHROPIC_BASE_URL,
        model=DEFAULT_ANTHROPIC_MODEL,
        api_key=None,
        auth_token=None,
    )

    assert config.auth_kwargs() == {}
    assert config.configured_credential() is None


def test_settings_from_env_defaults_to_anthropic(clean_settings_env, monkeypatch) -> None:
    monkeypatch.setattr(settings_module, "load_project_env", lambda: None)

    settings = Settings.from_env()

    assert settings.llm_provider == NOCODE_LLM_ANTHROPIC
    assert settings.anthropic().base_url == DEFAULT_ANTHROPIC_BASE_URL
    assert settings.anthropic().model == DEFAULT_ANTHROPIC_MODEL
    assert settings.moonshot().base_url == DEFAULT_MOONSHOT_BASE_URL
    assert settings.moonshot().model == DEFAULT_MOONSHOT_MODEL


def test_settings_from_env_uses_moonshot_provider(clean_settings_env, monkeypatch) -> None:
    monkeypatch.setattr(settings_module, "load_project_env", lambda: None)
    monkeypatch.setenv("NOCODE_LLM", "moonshot")
    monkeypatch.setenv("MOONSHOT_API_KEY", "moon-key")

    settings = Settings.from_env()

    assert settings.llm_provider == NOCODE_LLM_MOONSHOT
    assert settings.active_config() == settings.moonshot()
    assert settings.moonshot().configured_credential() == "moon-key"


def test_settings_from_env_treats_kimi_as_moonshot(clean_settings_env, monkeypatch) -> None:
    monkeypatch.setattr(settings_module, "load_project_env", lambda: None)
    monkeypatch.setenv("NOCODE_LLM", "kimi")

    settings = Settings.from_env()

    assert settings.llm_provider == NOCODE_LLM_MOONSHOT


def test_settings_from_env_uses_moonshot_model_for_anthropic_compatible_kimi(
    clean_settings_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings_module, "load_project_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.moonshot.cn/anthropic")

    settings = Settings.from_env()

    assert settings.anthropic().base_url == "https://api.moonshot.cn/anthropic/"
    assert settings.anthropic().model == DEFAULT_MOONSHOT_MODEL


def test_settings_from_env_uses_moonshot_model_for_kimi_coding_base(
    clean_settings_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings_module, "load_project_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.kimi.com/coding")

    settings = Settings.from_env()

    assert settings.anthropic().base_url == "https://api.kimi.com/coding/"
    assert settings.anthropic().model == DEFAULT_MOONSHOT_MODEL


def test_format_for_cli_for_moonshot_branch() -> None:
    settings = Settings(
        llm_provider=NOCODE_LLM_MOONSHOT,
        provider_configs={
            NOCODE_LLM_ANTHROPIC: AnthropicConfig(
                base_url=DEFAULT_ANTHROPIC_BASE_URL,
                model=DEFAULT_ANTHROPIC_MODEL,
                api_key=None,
                auth_token=None,
            ),
            NOCODE_LLM_MOONSHOT: MoonshotConfig(
                base_url=DEFAULT_MOONSHOT_BASE_URL,
                model=DEFAULT_MOONSHOT_MODEL,
                api_key="moon-key",
            ),
        },
    )

    rendered = settings.format_for_cli()

    assert "NOCODE_LLM: moonshot" in rendered
    assert f"POST {DEFAULT_MOONSHOT_BASE_URL}/chat/completions" in rendered
    assert "MOONSHOT_API_KEY: (已设置)" in rendered


def test_format_for_cli_for_anthropic_branch_includes_warning() -> None:
    settings = Settings(
        llm_provider=NOCODE_LLM_ANTHROPIC,
        provider_configs={
            NOCODE_LLM_ANTHROPIC: AnthropicConfig(
                base_url="https://api.openai.com",
                model=DEFAULT_ANTHROPIC_MODEL,
                api_key=None,
                auth_token=None,
            ),
            NOCODE_LLM_MOONSHOT: MoonshotConfig(
                base_url=DEFAULT_MOONSHOT_BASE_URL,
                model=DEFAULT_MOONSHOT_MODEL,
                api_key=None,
            ),
        },
    )

    rendered = settings.format_for_cli()

    assert "NOCODE_LLM: anthropic" in rendered
    assert "POST https://api.openai.com/v1/messages" in rendered
    assert "ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN: (未设置)" in rendered
    assert "WARNING:" in rendered
