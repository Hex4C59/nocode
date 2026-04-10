"""Tests for the CLI entrypoint argument handling and dispatch."""

from __future__ import annotations

import sys
import types

from nocode import cli as cli_module


def test_main_prints_version(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["nocode", "--version"])
    monkeypatch.setattr(cli_module, "version", lambda _name: "1.2.3")

    cli_module.main()

    assert capsys.readouterr().out == "1.2.3\n"


def test_main_prints_effective_config(capsys, monkeypatch) -> None:
    class FakeSettings:
        @classmethod
        def from_env(cls) -> "FakeSettings":
            return cls()

        def format_for_cli(self) -> str:
            return "effective config"

    monkeypatch.setattr(sys, "argv", ["nocode", "--print-config"])
    monkeypatch.setattr(cli_module, "load_project_env", lambda: None)
    monkeypatch.setattr(cli_module, "Settings", FakeSettings)

    cli_module.main()

    assert capsys.readouterr().out == "effective config\n"


def test_main_runs_tui_by_default(monkeypatch) -> None:
    called: list[str] = []
    fake_tui = types.ModuleType("nocode.tui")
    fake_tui.run_tui = lambda: called.append("run")  # type: ignore[attr-defined]

    monkeypatch.setattr(sys, "argv", ["nocode"])
    monkeypatch.setattr(cli_module, "load_project_env", lambda: None)
    monkeypatch.setitem(sys.modules, "nocode.tui", fake_tui)

    cli_module.main()

    assert called == ["run"]
