from __future__ import annotations

"""
BacktestRunner - runs one BacktestConfig and returns a structured
BacktestResult. Reuses the existing engine components (strategies,
PortfolioRouter, RiskManager, FillEngine, analytics) rather than
duplicating them; only the orchestration loop is re-implemented here so it
*returns data* instead of printing (the replay simulator keeps its own
print loop and is untouched).

Tick sources are unified behind `_iter_ticks`, which yields:
    (game, market, micro_regime, vol_regime, liquidity_depth, spread, stale)
for scenarios (simulated + scripted) and for replay bundles.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple

from src.backtest.config import BacktestConfig
from src.backtest.result import (
    BacktestResult, PnLSummary, DrawdownSummary, StrategyMetric, RegimeMetric, RiskEvent,
)
from src.models import GameState, MarketState
from src.engine.features import FeatureExtractor
from src.engine.router import PortfolioRouter, PortfolioState
from src.engine.risk import RiskManager, RiskConfig
from src.analytics.pnl import PnLTracker, Trade
from src.analytics.exposure import ExposureTracker
from src.analytics.performance import PerformanceAnalyzer
from src.simulation.fill_engine import FillEngine
from src.simulation.slippage import SlippageModel
from src.simulation.latency import LatencyModel
from src.simulation.volatility import VolatilityRegime
from src.simulation.market_regime import MarketRegime, RegimeClassifier, RegimeInputs
from src.strategies import (
    FavoriteGrinder, EndgameBonding, MomentumStrategy, OverpricedFade, LiquidityVacuum,
)

_STRATEGY_CLASSES = {
    "favorite_grinder": FavoriteGrinder,
    "endgame_bonding": EndgameBonding,
    "momentum": MomentumStrategy,
    "overpriced_fade": OverpricedFade,
    "liquidity_vacuum": LiquidityVacuum,
}

# Tick payload yielded by the source.
SourceTick = Tuple[GameState, MarketState, MarketRegime, VolatilityRegime, int, float, bool]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_strategies(active: List[str]) -> list:
    return [_STRATEGY_CLASSES[name]() for name in active if name in _STRATEGY_CLASSES]


class _StrategyAccount:
    """Per-strategy bookkeeping for attribution (marked at final price)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.trades = 0          # actionable signals routed to an intent
        self.fills = 0
        self.edge_sum = 0.0
        self.slippage_loss = 0.0
        self.regime_pnl: Dict[str, float] = {}
        # open lots: (market_id, signed_size, entry_price)
        self.lots: List[Tuple[str, int, float]] = []
        self.fill_regimes: List[str] = []

    def add_fill(self, market_id: str, signed_size: int, entry_price: float, regime: str) -> None:
        self.fills += 1
        self.lots.append((market_id, signed_size, entry_price))
        self.fill_regimes.append(regime)


class BacktestRunner:
    def __init__(self) -> None:
        self._classifier = RegimeClassifier()
        self._features = FeatureExtractor()

    # -- public ---------------------------------------------------------
    def run(self, config: BacktestConfig) -> BacktestResult:
        started = _now()
        result = BacktestResult(config=config, started_at=started, completed_at=started)

        active = config.active_strategies()
        strategies = make_strategies(active)
        strat_map = {s.NAME: s for s in strategies}
        accounts = {s.NAME: _StrategyAccount(s.NAME) for s in strategies}

        router = PortfolioRouter(max_concurrent_strategies=config.max_positions, cooldown_ticks=1)
        risk = RiskManager(RiskConfig(max_drawdown=300.0, min_liquidity_depth=20, max_slippage_cents=15.0))
        fill_engine = FillEngine(
            slippage=SlippageModel(impact_coeff=config.slippage_impact),
            latency=LatencyModel(base_ms=config.latency_ms, seed=config.seed),
        )
        fill_engine.fee_per_contract = config.fee_cents_per_contract
        slippage = SlippageModel(impact_coeff=config.slippage_impact)

        pnl = PnLTracker()
        exposure = ExposureTracker()
        perf = PerformanceAnalyzer()
        portfolio = PortfolioState()

        regime_acc: Dict[str, RegimeMetric] = {}
        final_marks: Dict[str, float] = {}
        prev_equity = 0.0
        n_ticks = 0

        try:
            ticks = list(self._iter_ticks(config))
        except Exception as exc:  # noqa: BLE001 - surfaced as a warning, not a crash
            result.warnings.append(f"failed to load ticks: {exc}")
            result.completed_at = _now()
            return result

        if not ticks:
            result.warnings.append("no ticks produced by source")

        for i, (game, market, regime, vol_regime, depth, spread, stale) in enumerate(ticks, 1):
            n_ticks = i
            fill_engine.current_regime = vol_regime
            fill_engine.book_depth = max(5, int(depth * 0.2))
            final_marks[market.market_id] = market.mid

            rm = regime_acc.setdefault(regime.value, RegimeMetric(regime.value))
            rm.ticks += 1

            fs = self._features.extract(game, market)
            signals = [s.evaluate(fs, regime=regime) for s in strategies]
            intents = router.allocate(signals, strat_map, regime, portfolio)
            result.trades += len(intents)

            for intent in intents:
                acct = accounts.get(intent.strategy_name)
                if acct is not None:
                    acct.trades += 1
                sig = next((s for s in signals if s.signal_id == intent.signal_id), None)
                if acct is not None and sig is not None:
                    acct.edge_sum += abs(sig.edge)

                slip = slippage.estimate(intent.price, intent.size, depth, vol_regime)
                ok, reason = risk.evaluate(
                    intent, spread=spread, regime=regime,
                    liquidity_depth=depth, expected_slippage=slip.slippage_cents,
                )
                if not ok:
                    result.rejected_orders += 1
                    result.risk_events.append(RiskEvent(i, "VETO", reason, intent.strategy_name))
                    continue

                exec_result = fill_engine.submit(intent)
                if exec_result.filled_size is None or exec_result.filled_size <= 0:
                    result.rejected_orders += 1
                    continue

                result.fills += 1
                rm.fills += 1
                price = exec_result.filled_price or intent.price
                size = exec_result.filled_size
                trade = Trade(market.market_id, intent.strategy_name, intent.side, price, size, exec_result.fee)
                pnl.record(trade, requested_price=intent.price)
                exposure.add(market.market_id, intent.strategy_name, intent.side, price, size)

                if acct is not None:
                    signed = size if intent.side.value == "YES" else -size
                    acct.add_fill(market.market_id, signed, price, regime.value)
                    acct.slippage_loss += abs(price - intent.price) * size

            equity = pnl.total_pnl(final_marks)
            perf.record_equity(equity)
            rm.pnl_cents += equity - prev_equity
            prev_equity = equity
            risk.state.update_equity(equity)

        # ---- finalize -------------------------------------------------
        result.ticks_processed = n_ticks
        self._finalize(result, config, pnl, perf, accounts, regime_acc, final_marks)
        result.completed_at = _now()
        return result

    # -- finalize -------------------------------------------------------
    def _finalize(self, result, config, pnl, perf, accounts, regime_acc, marks) -> None:
        unrealized = pnl.unrealized(marks)
        realized = pnl.realized_total
        total = realized + unrealized - pnl.fees_total
        bankroll = config.starting_bankroll_cents or 1.0

        result.pnl_summary = PnLSummary(
            total_pnl_cents=round(total, 2),
            realized_pnl_cents=round(realized, 2),
            unrealized_pnl_cents=round(unrealized, 2),
            fees_cents=round(pnl.fees_total, 2),
            slippage_loss_cents=round(pnl.slippage_loss, 2),
            sharpe_like=perf.sharpe_like(),
            return_on_bankroll_pct=round(100.0 * total / bankroll, 4),
        )
        result.drawdown_summary = DrawdownSummary(
            max_drawdown_cents=round(perf.drawdown.max_drawdown, 2),
            max_drawdown_pct=perf.drawdown.max_drawdown_pct(),
        )

        # Per-strategy attribution: mark each lot to the final mid.
        for name, acct in accounts.items():
            sm = StrategyMetric(
                strategy_name=name, trades=acct.trades, fills=acct.fills,
                edge_sum=round(acct.edge_sum, 3), slippage_loss_cents=round(acct.slippage_loss, 2),
            )
            for (market_id, signed, entry), regime in zip(acct.lots, acct.fill_regimes):
                mark = marks.get(market_id, entry)
                lot_pnl = signed * (mark - entry)
                sm.total_pnl_cents += lot_pnl
                sm.regime_pnl[regime] = sm.regime_pnl.get(regime, 0.0) + lot_pnl
                if lot_pnl > 0:
                    sm.wins += 1
                elif lot_pnl < 0:
                    sm.losses += 1
                result.fill_pnls.append(lot_pnl)
            sm.total_pnl_cents = round(sm.total_pnl_cents, 2)
            sm.regime_pnl = {k: round(v, 2) for k, v in sm.regime_pnl.items()}
            result.strategy_metrics.append(sm)

        result.regime_metrics = [
            RegimeMetric(r.regime, r.ticks, r.fills, round(r.pnl_cents, 2))
            for r in regime_acc.values()
        ]

    # -- tick sources ---------------------------------------------------
    def _iter_ticks(self, config: BacktestConfig) -> Iterator[SourceTick]:
        if config.bundle_path:
            yield from self._bundle_ticks(config.bundle_path)
        elif config.scenario_name in ("comeback", "blowout"):
            yield from self._scripted_ticks(config.scenario_name)
        elif config.scenario_name:
            yield from self._simulated_ticks(config.scenario_name, config.seed)
        else:
            raise ValueError("config must set scenario_name or bundle_path")

    def _simulated_ticks(self, scenario: str, seed: int) -> Iterator[SourceTick]:
        from src.replay.scenario_engine import ScenarioEngine
        engine = ScenarioEngine(seed=seed)
        for game, markets, ctx in engine.generate(scenario):
            yield (game, markets[0], ctx.micro_regime, ctx.vol_regime,
                   ctx.liquidity.depth, ctx.spread, ctx.liquidity.is_collapsed)

    def _scripted_ticks(self, scenario: str) -> Iterator[SourceTick]:
        from src.replay.sample_data_loader import SampleDataLoader
        loader = SampleDataLoader()
        ticks = loader.load_blowout() if scenario == "blowout" else loader.load_nfl_comeback()
        prev_mid = None
        for game, markets in ticks:
            m = markets[0]
            regime = self._classify(game, m, prev_mid)
            prev_mid = m.mid
            depth = max(1, m.open_interest or m.volume)
            yield (game, m, regime, VolatilityRegime.CALM, depth, m.spread, False)

    def _bundle_ticks(self, path: str) -> Iterator[SourceTick]:
        from src.data.bundle import load_bundle, tick_to_engine
        bundle = load_bundle(path)
        prev_mid = None
        for ctick in bundle.ticks:
            game, market = tick_to_engine(ctick)
            regime = self._classify(game, market, prev_mid)
            prev_mid = market.mid
            depth = max(1, market.open_interest or market.volume)
            stale = bool(ctick.metadata.get("stale_market") or ctick.metadata.get("stale_game"))
            yield (game, market, regime, VolatilityRegime.CALM, depth, market.spread, stale)

    def _classify(self, game: GameState, market: MarketState, prev_mid: Optional[float]) -> MarketRegime:
        odds_velocity = 0.0 if prev_mid is None else (market.mid - prev_mid) / 90.0
        return self._classifier.classify(RegimeInputs(
            spread=market.spread, odds_velocity=odds_velocity,
            liquidity_depth=max(1, market.open_interest or market.volume),
            volatility=abs(odds_velocity) * 60.0, time_remaining=game.clock_seconds,
            score_diff=game.score_diff, order_flow_imbalance=max(-1.0, min(1.0, odds_velocity * 10.0)),
            mid_price=market.mid,
        ))


def run_config(config: BacktestConfig) -> BacktestResult:
    return BacktestRunner().run(config)
