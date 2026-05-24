from __future__ import annotations

from typing import Protocol
from src.models import OrderIntent, ExecutionResult, OrderStatus


class ExecutionAdapter(Protocol):
    def submit(self, intent: OrderIntent) -> ExecutionResult: ...


class ExecutionEngine:
    """
    Wraps the active adapter. Defaults to fake execution in all environments
    unless explicitly configured otherwise.
    """

    def __init__(self, adapter: ExecutionAdapter | None = None) -> None:
        if adapter is None:
            from src.adapters.mock_execution_adapter import MockExecutionAdapter
            adapter = MockExecutionAdapter()
        self._adapter = adapter

    def submit(self, intent: OrderIntent) -> ExecutionResult:
        return self._adapter.submit(intent)
