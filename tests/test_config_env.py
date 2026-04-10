"""Tests for environment loading and project-root helpers."""

from __future__ import annotations

from pathlib import Path

from nocode.config import env as env_module


def test_project_root_points_at_repo() -> None:
    root = env_module.project_root()

    assert root.name == "nocode"
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "nocode").is_dir()


def test_load_project_env_is_idempotent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ANTHROPIC_API_KEY=test-key\n", encoding="utf-8")

    calls: list[tuple[Path, str | None]] = []

    def fake_load_dotenv(path: Path, encoding: str | None = None) -> None:
        calls.append((path, encoding))

    monkeypatch.setattr(env_module, "_loaded", False)
    monkeypatch.setattr(env_module, "project_root", lambda: tmp_path)
    monkeypatch.setattr(env_module, "load_dotenv", fake_load_dotenv)

    env_module.load_project_env()
    env_module.load_project_env()

    assert calls == [(env_path, "utf-8")]
