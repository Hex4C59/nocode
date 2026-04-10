"""CLI entry point for starting the local `nocode` Textual application."""

import argparse
from importlib.metadata import PackageNotFoundError, version

from nocode.config import Settings, load_project_env


def main() -> None:
    """Parse CLI arguments and launch the Textual UI by default."""
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
        print(Settings.from_env().format_for_cli())
        return
    from nocode.tui import run_tui

    run_tui()