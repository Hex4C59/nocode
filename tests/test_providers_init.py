"""Tests for provider registration and active-provider construction."""

from __future__ import annotations

from nocode.config.settings import AnthropicConfig, Settings
from nocode.providers import get_provider, register_provider


def test_register_provider_and_get_provider_uses_active_settings_config() -> None:
    config = AnthropicConfig(
        base_url="https://api.anthropic.com",
        model="claude-sonnet-4-20250514",
        api_key="test-key",
        auth_token=None,
    )
    seen_configs: list[AnthropicConfig] = []
    provider = object()
    provider_id = "test-provider"

    def factory(active_config: AnthropicConfig) -> object:
        seen_configs.append(active_config)
        return provider

    register_provider(provider_id, factory)
    settings = Settings(llm_provider=provider_id, provider_configs={provider_id: config})

    assert get_provider(settings) is provider
    assert seen_configs == [config]
