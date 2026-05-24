from __future__ import annotations

from src.models import OrderIntent, ExecutionResult, OrderStatus


class MockExecutionAdapter:
    """Fake execution — always fills at limit price with zero fee."""

    def submit(self, intent: OrderIntent) -> ExecutionResult:
        print(
            f"  [FAKE EXEC] {intent.side.value} {intent.size}x {intent.market_id}"
            f" @ {intent.price:.1f}¢  (strategy={intent.strategy_name})"
        )
        return ExecutionResult(
            intent_id=intent.intent_id,
            market_id=intent.market_id,
            status=OrderStatus.FILLED,
            filled_price=intent.price,
            filled_size=intent.size,
            fee=0.0,
            message="mock fill",
        )
