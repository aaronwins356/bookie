from __future__ import annotations

"""
Tool registry for the local brain (future LLM controller).

Each tool is a plain callable. The brain calls tools by name; all
deterministic logic (risk, execution) is enforced downstream —
the brain cannot bypass it by choosing a different tool.
"""

from typing import Callable, Dict, Any


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name!r}. Available: {list(self._tools)}")
        return self._tools[name](**kwargs)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
