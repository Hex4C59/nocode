# 项目根目录与 .env 加载：与当前工作目录无关，保证从任意目录启动都能找到仓库内 .env。
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

_loaded = False

# Anthropic Python SDK 将 base_url 的路径与相对路径 `v1/messages` 直接拼接（中间不自动补 `/`）。
# 故 `…/anthropic` 必须规范为 `…/anthropic/`，否则会请求 `…/anthropicv1/messages`（404）。
# 若此处误含末尾 `/v1` 会叠成 `/v1/v1/messages`（404）。
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


def project_root() -> Path:
    """本文件位于 `src/nocode/env.py`，向上三级目录为仓库根。"""
    return Path(__file__).resolve().parent.parent.parent


def load_project_env() -> None:
    """从仓库根目录加载 `.env`（UTF-8），幂等。"""
    global _loaded
    if _loaded:
        return
    env_path = project_root() / ".env"
    if env_path.is_file():
        load_dotenv(env_path, encoding="utf-8")
    _loaded = True


def anthropic_sdk_auth_kwargs() -> dict[str, str]:
    """
    传给 `AsyncAnthropic`：优先 `api_key`（X-Api-Key），否则 `auth_token`（Bearer）。
    勿把 `ANTHROPIC_AUTH_TOKEN` 误传入 `api_key`（Moonshot 常需 Bearer）。
    """
    load_project_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return {"api_key": api_key}
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if token:
        return {"auth_token": token}
    return {}


def anthropic_api_key() -> str | None:
    """
    当前用于鉴权的字符串（优先 API Key）；CLI 仅用于展示是否已配置。
    """
    kw = anthropic_sdk_auth_kwargs()
    return kw.get("api_key") or kw.get("auth_token")


def normalize_anthropic_base_url(raw: str | None) -> str | None:
    """去掉末尾多余的 `/v1`；子路径网关须以 `/` 结尾以便 SDK 正确拼出 `/…/v1/messages`。"""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    while s.endswith("/"):
        s = s[:-1]
    if s.endswith("/v1"):
        s = s[:-3]
        while s.endswith("/"):
            s = s[:-1]
    try:
        parsed = urlparse(s)
    except ValueError:
        return s if s.endswith("/") else f"{s}/"
    path = (parsed.path or "").rstrip("/")
    if path:
        s = f"{s}/"
    return s


def resolved_anthropic_base_url() -> str:
    """最终传给 `AsyncAnthropic(base_url=...)` 的根地址。"""
    load_project_env()
    raw = os.environ.get("ANTHROPIC_BASE_URL")
    normalized = normalize_anthropic_base_url(raw)
    if normalized is None:
        return DEFAULT_ANTHROPIC_BASE_URL
    return normalized


# 常见「仅 OpenAI 兼容」的网关主机，不提供 Anthropic `/v1/messages`；误填会导致 404。
# Moonshot 单独判断：同一主机上既有 `/v1`（OpenAI）也有 `/anthropic`（Messages）。
_INCOMPATIBLE_ANTHROPIC_HOST_SUFFIXES: tuple[str, ...] = (
    "api.openai.com",
    "openrouter.ai",
    "api.deepseek.com",
    "generativelanguage.googleapis.com",
)


def _moonshot_host(hostname: str) -> bool:
    h = hostname.lower()
    return h == "api.moonshot.cn" or h == "api.moonshot.ai" or h.endswith(
        ".moonshot.cn",
    ) or h.endswith(".moonshot.ai")


def is_moonshot_anthropic_messages_base(resolved_base_url: str) -> bool:
    """是否为 Moonshot 提供的 Anthropic Messages 兼容根路径（与 Claude Code 一致）。"""
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
    """Kimi Code 订阅文档中的 `api.kimi.com/coding` Messages 兼容入口。"""
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
    """若 BASE_URL 明显不是 Anthropic Messages API，返回简短说明供 CLI / 错误提示使用。"""
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
            "https://api.moonshot.cn/anthropic，以控制台为准），"
            "不要只填 …/v1（那是 OpenAI 兼容的 chat/completions）。"
            "若要用 OpenAI 协议走 Kimi，可设 NOCODE_LLM=moonshot 与 MOONSHOT_*。"
        )

    for suffix in _INCOMPATIBLE_ANTHROPIC_HOST_SUFFIXES:
        if host == suffix or host.endswith("." + suffix):
            return (
                "当前 BASE_URL 指向常见「OpenAI 兼容」网关，不提供 Anthropic 的 /v1/messages，"
                "因此会 404。请删除 ANTHROPIC_BASE_URL 并改用 Anthropic 官方 Key（直连 "
                f"{DEFAULT_ANTHROPIC_BASE_URL}），或换用支持 Anthropic 协议的中转。"
            )
    return None


# --- LLM 提供方：Anthropic Messages API vs Moonshot（Kimi）OpenAI 兼容接口 ---
NOCODE_LLM_ANTHROPIC = "anthropic"
NOCODE_LLM_MOONSHOT = "moonshot"

DEFAULT_MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MOONSHOT_MODEL = "kimi-k2.5"


def resolved_llm_provider() -> str:
    """
    `NOCODE_LLM` 或 `LLM_PROVIDER`：`anthropic`（默认）| `moonshot`（Kimi，chat/completions）。
    也可用别名 `kimi` 表示 moonshot。
    """
    load_project_env()
    v = os.environ.get("NOCODE_LLM", os.environ.get("LLM_PROVIDER", "")).strip().lower()
    if v in ("moonshot", "kimi"):
        return NOCODE_LLM_MOONSHOT
    return NOCODE_LLM_ANTHROPIC


def moonshot_api_key() -> str | None:
    load_project_env()
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if key:
        return key
    return None


def resolved_moonshot_base_url() -> str:
    """OpenAI 兼容客户端使用的 base_url，须包含 `/v1` 后缀（与 Moonshot 文档一致）。"""
    load_project_env()
    raw = os.environ.get("MOONSHOT_BASE_URL", "").strip()
    if not raw:
        return DEFAULT_MOONSHOT_BASE_URL
    return raw.rstrip("/")


def resolved_moonshot_model() -> str:
    load_project_env()
    m = os.environ.get("MOONSHOT_MODEL", "").strip()
    if m:
        return m
    return DEFAULT_MOONSHOT_MODEL
