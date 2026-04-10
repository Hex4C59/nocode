import argparse
from importlib.metadata import PackageNotFoundError, version

from nocode.tui_app import run_tui


def main() -> None:
    """解析命令行参数：默认进入 TUI；--version 打印版本后退出。"""
    parser = argparse.ArgumentParser(prog="nocode", description="终端 coding agent（TUI）")
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="打印版本号并退出",
    )
    args = parser.parse_args()
    if args.version:
        try:
            print(version("nocode"))
        except PackageNotFoundError:
            print("0.0.0")
        return
    run_tui()