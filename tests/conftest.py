"""Shared pytest fixtures for the `nocode` test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

SETTINGS_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "LLM_PROVIDER",
    "MOONSHOT_API_KEY",
    "MOONSHOT_BASE_URL",
    "MOONSHOT_MODEL",
    "NOCODE_LLM",
)


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Provide a temporary workspace path for tool tests."""
    return tmp_path


@pytest.fixture
def clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear provider-related environment variables before each config test."""
    for key in SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
