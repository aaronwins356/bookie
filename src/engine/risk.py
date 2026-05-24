from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional
from src.models import OrderIntent, OrderStatus
from src.simulation.market_regime import MarketRegime


# Default per-regime risk multipliers. <1 shrinks size, 0 disables trading.
# Conservative in chaos/collapse, full size in calm/normal conditions.
DEFAULT_REGIME_RISK_SCALE: Dict[MarketRegime, float] = {
    MarketRegime.CALM: 1.0,
    MarketRegime.TRENDING_UP: 0.9,
    MarketRegime.TRENDING_DOWN: 0.9,
    MarketRegime.MEAN_REVERSION: 0.8,
    MarketRegime.FAVORITE_EUPHORIA: 0.6,
    MarketRegime.PANIC_BUYING: 0.5,
    MarketRegime.PANIC_SELLING: 0.5,
    MarketRegime.ENDGAME_CHAOS: 0.4,
    MarketRegime.LIQUIDITY_COLLAPSE: 0.3,
    MarketRegime.DEAD_MARKET: 0.7,
}


@dataclass
class RiskConfig:
    max_position_per_market: int = 100    # max contracts held in one market
    max_order_size: int = 50
    max_price_cents: float = 90.0        # never buy YES above this
    min_price_cents: float = 10.0        # never buy NO above equivalent
    max_daily_loss: float = 500.0        # dollars
    spread_filter: float = 5.0           # reject if spread > this

    # ---- extended risk controls (permissive defaults = no-op) --------
    max_drawdown: float = 1e9            # dollars peak-to-trough
    catastrophic_loss_limit: float = 1e9  # single-event loss kill switch
    min_liquidity_depth: int = 0         # reject if available depth below this
    max_slippage_cents: float = 1e9      # reject if expected slippage above this
    max_strategy_exposure: float = 1e9   # max notional ($) per strategy
    regime_risk_scale: Dict[MarketRegime, float] = field(
        default_factory=lambda: dict(DEFAULT_REGIME_RISK_SCALE)
    )


@dataclass
class RiskState:
    positions: Dict[str, int] = field(default_factory=dict)   # market_id -> net contracts
    daily_pnl: float = 0.0
    equity: float = 0.0
    peak_equity: float = 0.0
    max_drawdown_seen: float = 0.0
    strategy_exposure: Dict[str, float] = field(default_factory=dict)  # strategy -> notional $

    def net_position(self, market_id: str) -> int:
        return self.positions.get(market_id, 0)

    def record_fill(self, market_id: str, size: int, pnl_delta: float = 0.0) -> None:
        self.positions[market_id] = self.net_position(market_id) + size
        self.daily_pnl += pnl_delta

    def update_equity(self, equity: float) -> float:
        self.equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
        dd = self.peak_equity - equity
        if dd > self.max_drawdown_seen:
            self.max_drawdown_seen = dd
        return dd

    def add_exposure(self, strategy: str, notional: float) -> None:
        self.strategy_exposure[strategy] = self.strategy_exposure.get(strategy, 0.0) + notional


class RiskManager:
    """
    Deterministic gatekeeper. The local brain CANNOT override these rules.
    Returns (approved: bool, reason: str).

    The extended checks (drawdown, liquidity, slippage, exposure,
    catastrophic loss) only fire when the relevant inputs are supplied or
    the relevant config is tightened, so the base contract is unchanged.
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.state = RiskState()

    def evaluate(
        self,
        intent: OrderIntent,
        spread: float = 0.0,
        regime: Optional[MarketRegime] = None,
        liquidity_depth: Optional[int] = None,
        expected_slippage: float = 0.0,
    ) -> Tuple[bool, str]:
        c = self.config

        if intent.size > c.max_order_size:
            return False, f"size {intent.size} > max {c.max_order_size}"

        if intent.price > c.max_price_cents:
            return False, f"price {intent.price} > max {c.max_price_cents}"

        if intent.price < c.min_price_cents:
            return False, f"price {intent.price} < min {c.min_price_cents}"

        if spread > c.spread_filter:
            return False, f"spread {spread:.1f} > filter {c.spread_filter}"

        current_pos = self.state.net_position(intent.market_id)
        if abs(current_pos + intent.size) > c.max_position_per_market:
            return False, f"position would exceed {c.max_position_per_market}"

        if self.state.daily_pnl < -c.max_daily_loss:
            return False, f"daily loss limit hit ({self.state.daily_pnl:.2f})"

        # ---- extended deterministic checks -------------------------------
        if self.state.max_drawdown_seen > c.max_drawdown:
            return False, f"max drawdown breached ({self.state.max_drawdown_seen:.2f})"

        if self.state.daily_pnl < -c.catastrophic_loss_limit:
            return False, f"catastrophic loss kill-switch ({self.state.daily_pnl:.2f})"

        if liquidity_depth is not None and liquidity_depth < c.min_liquidity_depth:
            return False, f"liquidity depth {liquidity_depth} < min {c.min_liquidity_depth}"

        if expected_slippage > c.max_slippage_cents:
            return False, f"slippage {expected_slippage:.1f} > max {c.max_slippage_cents}"

        notional = intent.price * intent.size / 100.0
        current_exp = self.state.strategy_exposure.get(intent.strategy_name, 0.0)
        if current_exp + notional > c.max_strategy_exposure:
            return False, f"strategy exposure would exceed {c.max_strategy_exposure}"

        if regime is not None and c.regime_risk_scale.get(regime, 1.0) <= 0.0:
            return False, f"regime {regime.value} trading disabled"

        return True, "approved"

    # ---- deterministic sizing helpers (advisory; never bypass evaluate) --
    def regime_scale(self, regime: Optional[MarketRegime]) -> float:
        if regime is None:
            return 1.0
        return self.config.regime_risk_scale.get(regime, 1.0)

    def volatility_adjusted_size(
        self,
        base_size: int,
        regime: Optional[MarketRegime] = None,
        volatility: float = 1.0,
        liquidity_depth: Optional[int] = None,
    ) -> int:
        """Scale a base size down for regime risk, high volatility, and thin books."""
        size = base_size * self.regime_scale(regime)

        if volatility > 1.0:
            size /= volatility   # higher vol → smaller size

        if liquidity_depth is not None and liquidity_depth > 0:
            # never take more than 10% of visible depth
            size = min(size, liquidity_depth * 0.1)

        return max(1, int(size))
