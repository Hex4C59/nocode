"""Registry helpers for discovering built-in local tools."""

from __future__ import annotations

import importlib
import pkgutil

from nocode.tools import builtins as builtins_pkg
from nocode.tools.types import ToolSpec


def build_default_registry() -> dict[str, ToolSpec]:
    """Auto-discover built-in tools that export `SPEC`."""
    registry: dict[str, ToolSpec] = {}
    modules = sorted(pkgutil.iter_modules(builtins_pkg.__path__), key=lambda info: info.name)
    for module_info in modules:
        module = importlib.import_module(f"nocode.tools.builtins.{module_info.name}")
        spec = getattr(module, "SPEC", None)
        if spec is None:
            continue
        registry[spec.name] = spec
    return registry


def build_tool_params(registry: dict[str, ToolSpec]) -> list[dict[str, object]]:
    return [registry[name].as_tool_param() for name in registry]
