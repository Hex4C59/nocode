"""Provider registry and factory helpers for built-in LLM backends."""

from __future__ import annotations

from collections.abc import Callable

from nocode.config import ProviderConfig, Settings
from nocode.providers.base import LLMProvider

ProviderFactory = Callable[[ProviderConfig], LLMProvider]
_PROVIDER_REGISTRY: dict[str, ProviderFactory] = {}


def register_provider(provider_id: str, factory: ProviderFactory) -> None:
    """Register one provider factory by id."""
    _PROVIDER_REGISTRY[provider_id] = factory


def get_provider(settings: Settings) -> LLMProvider:
    """Instantiate the active provider from resolved settings."""
    provider_id = settings.llm_provider
    factory = _PROVIDER_REGISTRY[provider_id]
    return factory(settings.active_config())


from nocode.providers import anthropic as _anthropic  # noqa: F401,E402
from nocode.providers import moonshot as _moonshot  # noqa: F401,E402

__all__ = ["LLMProvider", "get_provider", "register_provider"]
