"""Shared fixtures for builtin tool handler tests."""

from __future__ import annotations

import pytest

from nocode.tools.types import ToolRuntime


@pytest.fixture
def runtime(tmp_workspace) -> ToolRuntime:
    """Provide a runtime bound to a temporary workspace."""
    return ToolRuntime(workspace_root=tmp_workspace)
