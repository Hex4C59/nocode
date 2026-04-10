"""Provider settings and normalization for the local `nocode` runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse

from nocode.config.env import load_project_env

NOCODE_LLM_ANTHROPIC = "anthropic"
NOCODE_LLM_MOONSHOT = "moonshot"

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MOONSHOT_MODEL = "kimi-k2.5"

_INCOMPATIBLE_ANTHROPIC_HOST_SUFFIXES: tuple[str, ...] = (
    "api.openai.com",
    "openrouter.ai",
    "api.deepseek.com",
    "generativelanguage.googleapis.com",
)


def _clean_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    return None


def normalize_anthropic_base_url(raw: str | None) -> str | None:
    """Normalize Anthropic-compatible base URLs for the Python SDK."""
    if raw is None:
        return None
    base_url = raw.strip()
    if not base_url:
        return None
    while base_url.endswith("/"):
        base_url = base_url[:-1]
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
        while base_url.endswith("/"):
            base_url = base_url[:-1]
    try:
        parsed = urlparse(base_url)
    except ValueError:
        return base_url if base_url.endswith("/") else f"{base_url}/"
    path = (parsed.path or "").rstrip("/")
    if path:
        return f"{base_url}/"
    return base_url


def _moonshot_host(hostname: str) -> bool:
    lowered = hostname.lower()
    return (
        lowered == "api.moonshot.cn"
        or lowered == "api.moonshot.ai"
        or lowered.endswith(".moonshot.cn")
        or lowered.endswith(".moonshot.ai")
    )


def is_moonshot_anthropic_messages_base(resolved_base_url: str) -> bool:
    """Report whether the base URL targets Moonshot's Anthropic endpoint."""
    try:
        parsed = urlparse(resolved_base_url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").rstrip("/")
    except ValueError:
        return False
    if not _moonshot_host(host):
        return False
    return path == "/anthropic" or path.endswith("/anthropic")


def is_kimi_coding_anthropic_base(resolved_base_url: str) -> bool:
    """Report whether the base URL targets Kimi Code's Anthropic endpoint."""
    try:
        parsed = urlparse(resolved_base_url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").rstrip("/")
    except ValueError:
        return False
    if host != "api.kimi.com":
        return False
    return path == "/coding" or path.endswith("/coding")


def anthropic_base_url_mismatch_hint(resolved_base_url: str) -> str | None:
    """Return a short hint when the base URL is unlikely to serve `/v1/messages`."""
    try:
        parsed = urlparse(resolved_base_url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").rstrip("/")
    except ValueError:
        return None
    if not host:
        return None

    if _moonshot_host(host):
        if path == "/anthropic" or path.endswith("/anthropic"):
            return None
        return (
            "当前为 Moonshot 主机但未使用 Anthropic Messages 路径。与 Claude Code 一致时请设置 "
            "ANTHROPIC_BASE_URL=https://api.moonshot.ai/anthropic（国内账号常用 "
            "https://api.moonshot.cn/anthropic，以控制台为准），不要只填 …/v1。"
            "若要用 OpenAI 协议走 Kimi，可设 NOCODE_LLM=moonshot 与 MOONSHOT_*。"
        )

    for suffix in _INCOMPATIBLE_ANTHROPIC_HOST_SUFFIXES:
        if host == suffix or host.endswith(f".{suffix}"):
            return (
                "当前 BASE_URL 指向常见 OpenAI 兼容网关，不提供 Anthropic 的 /v1/messages。"
                f" 请删除 ANTHROPIC_BASE_URL 并改用 {DEFAULT_ANTHROPIC_BASE_URL}，"
                "或切换到支持 Anthropic 协议的中转。"
            )
    return None


@dataclass(frozen=True, slots=True)
class AnthropicConfig:
    """Configuration for Anthropic-compatible Messages API providers."""

    base_url: str
    model: str
    api_key: str | None
    auth_token: str | None

    def auth_kwargs(self) -> dict[str, str]:
        if self.api_key:
            return {"api_key": self.api_key}
        if self.auth_token:
            return {"auth_token": self.auth_token}
        return {}

    def configured_credential(self) -> str | None:
        return self.api_key or self.auth_token

    def mismatch_hint(self) -> str | None:
        return anthropic_base_url_mismatch_hint(self.base_url)


@dataclass(frozen=True, slots=True)
class MoonshotConfig:
    """Configuration for Moonshot's OpenAI-compatible API."""

    base_url: str
    model: str
    api_key: str | None

    def configured_credential(self) -> str | None:
        return self.api_key


ProviderConfig = AnthropicConfig | MoonshotConfig


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings resolved from the environment."""

    llm_provider: str
    provider_configs: dict[str, ProviderConfig]

    @classmethod
    def from_env(cls) -> Settings:
        load_project_env()

        anthropic_base_url = normalize_anthropic_base_url(_clean_env("ANTHROPIC_BASE_URL"))
        if anthropic_base_url is None:
            anthropic_base_url = DEFAULT_ANTHROPIC_BASE_URL
        anthropic_model = _clean_env("ANTHROPIC_MODEL")
        if anthropic_model is None:
            if (
                is_moonshot_anthropic_messages_base(anthropic_base_url)
                or is_kimi_coding_anthropic_base(anthropic_base_url)
            ):
                anthropic_model = DEFAULT_MOONSHOT_MODEL
            else:
                anthropic_model = DEFAULT_ANTHROPIC_MODEL

        moonshot_base_url = _clean_env("MOONSHOT_BASE_URL")
        if moonshot_base_url is None:
            moonshot_base_url = DEFAULT_MOONSHOT_BASE_URL
        else:
            moonshot_base_url = moonshot_base_url.rstrip("/")
        moonshot_model = _clean_env("MOONSHOT_MODEL")
        if moonshot_model is None:
            moonshot_model = DEFAULT_MOONSHOT_MODEL

        provider_name = _clean_env("NOCODE_LLM") or _clean_env("LLM_PROVIDER")
        if provider_name in {"moonshot", "kimi"}:
            llm_provider = NOCODE_LLM_MOONSHOT
        else:
            llm_provider = NOCODE_LLM_ANTHROPIC

        provider_configs: dict[str, ProviderConfig] = {
            NOCODE_LLM_ANTHROPIC: AnthropicConfig(
                base_url=anthropic_base_url,
                model=anthropic_model,
                api_key=_clean_env("ANTHROPIC_API_KEY"),
                auth_token=_clean_env("ANTHROPIC_AUTH_TOKEN"),
            ),
            NOCODE_LLM_MOONSHOT: MoonshotConfig(
                base_url=moonshot_base_url,
                model=moonshot_model,
                api_key=_clean_env("MOONSHOT_API_KEY"),
            ),
        }
        return cls(llm_provider=llm_provider, provider_configs=provider_configs)

    def active_config(self) -> ProviderConfig:
        return self.provider_configs[self.llm_provider]

    def anthropic(self) -> AnthropicConfig:
        return cast(AnthropicConfig, self.provider_configs[NOCODE_LLM_ANTHROPIC])

    def moonshot(self) -> MoonshotConfig:
        return cast(MoonshotConfig, self.provider_configs[NOCODE_LLM_MOONSHOT])

    def format_for_cli(self) -> str:
        """Render the effective settings for `nocode --print-config`."""
        if self.llm_provider == NOCODE_LLM_MOONSHOT:
            config = self.moonshot()
            lines = [
                "NOCODE_LLM: moonshot (Kimi, OpenAI-compatible)",
                f"MOONSHOT_BASE_URL: {config.base_url}",
                f"effective request: POST {config.base_url}/chat/completions",
                f"MOONSHOT_MODEL: {config.model}",
                "MOONSHOT_API_KEY: "
                + ("(已设置)" if config.configured_credential() else "(未设置)"),
            ]
            return "\n".join(lines)

        config = self.anthropic()
        lines = [
            "NOCODE_LLM: anthropic",
            f"effective ANTHROPIC_BASE_URL: {config.base_url}",
            f"effective request: POST {config.base_url.rstrip('/')}/v1/messages",
            f"effective ANTHROPIC_MODEL: {config.model}",
            "ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN: "
            + ("(已设置)" if config.configured_credential() else "(未设置)"),
        ]
        hint = config.mismatch_hint()
        if hint:
            lines.extend(["", f"WARNING: {hint}"])
        return "\n".join(lines)
