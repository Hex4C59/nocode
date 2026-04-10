"""
命令行入口：解析最少参数，并在进入 TUI 前加载项目环境变量。
"""

import argparse
from importlib.metadata import PackageNotFoundError, version

from nocode.env import load_project_env


def main() -> None:
    """解析命令行参数：默认进入 TUI；--version 打印版本后退出。"""
    parser = argparse.ArgumentParser(prog="nocode", description="终端 coding agent（TUI）")
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="打印版本号并退出",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="打印生效的 API 根地址与模型（不含密钥）后退出",
    )
    args = parser.parse_args()
    if args.version:
        try:
            print(version("nocode"))
        except PackageNotFoundError:
            print("0.0.0")
        return
    load_project_env()
    if args.print_config:
        from nocode.env import (
            NOCODE_LLM_MOONSHOT,
            anthropic_api_key,
            anthropic_base_url_mismatch_hint,
            moonshot_api_key,
            resolved_anthropic_base_url,
            resolved_llm_provider,
            resolved_moonshot_base_url,
        )
        from nocode.streaming import effective_anthropic_model, effective_moonshot_model

        if resolved_llm_provider() == NOCODE_LLM_MOONSHOT:
            ms_base = resolved_moonshot_base_url().rstrip("/")
            print("NOCODE_LLM: moonshot (Kimi, OpenAI-compatible)")
            print(f"MOONSHOT_BASE_URL: {ms_base}")
            print(f"effective request: POST {ms_base}/chat/completions")
            print(f"MOONSHOT_MODEL: {effective_moonshot_model()}")
            print(
                "MOONSHOT_API_KEY:",
                "(已设置)" if moonshot_api_key() else "(未设置)",
            )
            return

        base = resolved_anthropic_base_url().rstrip("/")
        print("NOCODE_LLM: anthropic")
        print(f"effective ANTHROPIC_BASE_URL: {base}")
        print(f"effective request: POST {base}/v1/messages")
        print(f"effective ANTHROPIC_MODEL: {effective_anthropic_model()}")
        print(
            "ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN:",
            "(已设置)" if anthropic_api_key() else "(未设置)",
        )
        hint = anthropic_base_url_mismatch_hint(base)
        if hint:
            print()
            print("WARNING:", hint)
        return
    from nocode.tui_app import run_tui

    run_tui()