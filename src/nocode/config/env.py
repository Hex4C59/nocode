"""Environment helpers for locating the repo root and loading `.env` once."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_loaded = False


def project_root() -> Path:
    """Return the repository root from the installed package layout."""
    return Path(__file__).resolve().parents[3]


def load_project_env() -> None:
    """Load the repository `.env` file with UTF-8 encoding once per process."""
    global _loaded
    if _loaded:
        return
    env_path = project_root() / ".env"
    if env_path.is_file():
        load_dotenv(env_path, encoding="utf-8")
    _loaded = True
