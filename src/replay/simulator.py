from __future__ import annotations

"""
CLI replay simulator.

Scripted scenarios (hand-authored price paths):
    python -m src.replay.simulator --scenario comeback
    python -m src.replay.simulator --scenario blowout

Simulated scenarios (microstructure-driven, regime-aware, with slippage,
liquidity collapse, latency, events, and full analytics):
    python -m src.replay.simulator --scenario calm
    python -m src.replay.simulator --scenario panic
    python -m src.replay.simulator --scenario liquidity_crisis
    python -m src.replay.simulator --scenario endgame_chaos
"""

import argparse
from typing import Dict, List, Optional

from src.replay.sample_data_loader import SampleDataLoader
from src.replay.scenario_engine import ScenarioEngine
from src.strategies import (
    FavoriteGrinder, EndgameBonding, MomentumStrategy,
    OverpricedFade, LiquidityVacuum,
)
from src.engine.features import FeatureExtractor
from src.engine.router import Router, PortfolioRouter, PortfolioState
from src.engine.risk import RiskManager, RiskConfig
from src.engine.execution import ExecutionEngine
from src.engine.audit import AuditLog
from src.controller.tool_registry import ToolRegistry
from src.controller.local_brain import LocalBrain
from src.controller.decision_loop import DecisionLoop
from src.adapters.mock_execution_adapter import MockExecutionAdapter
from src.simulation.fill_engine import FillEngine
from src.simulation.slippage import SlippageModel
from src.simulation.volatility import VolatilityRegime
from src.simulation.market_regime import RegimeClassifier, RegimeInputs
from src.models import OrderSide
from src.analytics.pnl import PnLTracker, Trade
from src.analytics.exposure import ExposureTracker
from src.analytics.strategy_metrics import StrategyMetrics
from src.analytics.expectancy import ExpectancyCalculator
from src.analytics.performance import PerformanceAnalyzer
from src.storage.snapshot_store import SnapshotStore, TickSnapshot


DIVIDER = "=" * 64
SCRIPTED = {"comeback", "blowout"}


def _make_strategies() -> list:
    return [
        FavoriteGrinder(),
        EndgameBonding(),
        MomentumStrategy(),
        OverpricedFade(),
        LiquidityVacuum(),
    ]


def build_loop(execution_adapter: Optional[object] = None) -> DecisionLoop:
    """Build a DecisionLoop. Defaults to fake execution (backward compatible)."""
    registry = ToolRegistry()
    brain = LocalBrain(registry)
    router = Router()
    risk = RiskManager(RiskConfig())
    execution = ExecutionEngine(execution_adapter or MockExecutionAdapter())
    audit = AuditLog()
    return DecisionLoop(_make_strategies(), brain, router, risk, execution, audit)


# ---------------------------------------------------------------------------
# Scripted path (unchanged behavior for comeback / blowout).
# ---------------------------------------------------------------------------
def _run_scripted(scenario: str) -> None:
    loader = SampleDataLoader()
    ticks = loader.load_blowout() if scenario == "blowout" else loader.load_nfl_comeback()
    loop = build_loop()

    print(f"\n{DIVIDER}\n  BOOKIE REPLAY SIMULATOR  -  scenario={scenario}\n{DIVIDER}\n")

    for i, (game, markets) in enumerate(ticks, 1):
        print(f"--- TICK {i} ---")
        print(f"  GAME STATE  : {game.home_team} {game.home_score} vs "
              f"{game.away_team} {game.away_score}  [{game.phase.value}]  "
              f"clock={game.clock_seconds}s  diff={game.score_diff:+d}")
        for m in markets:
            print(f"  MARKET STATE: {m.market_id}  mid={m.mid:.1f}c  "
                  f"spread={m.spread:.1f}c  vol={m.volume}")

        signals, results = loop.tick(game, markets)
        print(f"  SIGNALS ({len(signals)}):")
        for s in signals:
            marker = "*" if s.is_actionable() else " "
            print(f"    [{marker}] {s.strategy_name:<22} {s.direction.value:<5} "
                  f"edge={s.edge:+.1f}  conf={s.confidence:.2f}  fair={s.fair_value:.1f}")
        actionable = [s for s in signals if s.is_actionable()]
        print(f"  ROUTER      : {len(actionable)} actionable signal(s) routed")
        if results:
            print(f"  EXECUTIONS  : {len(results)} fill(s)")
            for r in results:
                print(f"    => {r.market_id} status={r.status.value} "
                      f"price={r.filled_price}c size={r.filled_size}")
        else:
            print("  EXECUTIONS  : none")
        print()

    print(DIVIDER + "\n  AUDIT LOG\n" + DIVIDER)
    loop.audit.dump()
    print(f"\nReplay complete. {len(ticks)} tick(s) processed.\n")


# ---------------------------------------------------------------------------
# Simulated path (microstructure + analytics).
# ---------------------------------------------------------------------------
def _run_simulated(scenario: str, seed: int = 42) -> None:
    engine = ScenarioEngine(seed=seed)
    ticks = engine.generate(scenario)

    strategies = _make_strategies()
    strat_map: Dict[str, object] = {s.NAME: s for s in strategies}

    features = FeatureExtractor()
    registry = ToolRegistry()
    brain = LocalBrain(registry)
    router = PortfolioRouter(max_concurrent_strategies=3, cooldown_ticks=1)
    risk = RiskManager(RiskConfig(
        max_drawdown=300.0,
        min_liquidity_depth=40,
        max_slippage_cents=12.0,
    ))
    fill_engine = FillEngine()
    slippage = SlippageModel()
    audit = AuditLog()

    pnl = PnLTracker()
    exposure = ExposureTracker()
    strat_metrics = StrategyMetrics()
    expectancy = ExpectancyCalculator()
    perf = PerformanceAnalyzer()
    snapshots = SnapshotStore()
    portfolio = PortfolioState()

    print(f"\n{DIVIDER}\n  BOOKIE MICROSTRUCTURE SIMULATOR  -  scenario={scenario}  seed={seed}\n{DIVIDER}\n")

    n_fills = 0
    prev_equity = 0.0
    for game, markets, ctx in ticks:
        market = markets[0]
        fill_engine.current_regime = ctx.vol_regime
        fill_engine.book_depth = max(5, int(ctx.liquidity.depth * 0.1))

        print(f"--- TICK {ctx.tick} ---")
        print(f"  GAME STATE  : {game.home_team} {game.home_score} vs "
              f"{game.away_team} {game.away_score}  [{game.phase.value}]  "
              f"clock={game.clock_seconds}s  diff={game.score_diff:+d}")
        print(f"  MARKET STATE: {market.market_id}  mid={market.mid:.1f}c  "
              f"spread={market.spread:.1f}c  depth={ctx.liquidity.depth}  "
              f"vol_regime={ctx.vol_regime.value}")
        print(f"  REGIME      : {ctx.micro_regime.value}  "
              f"odds_velocity={ctx.odds_velocity:+.3f}c/s  "
              f"liquidity_mult={ctx.liquidity.depth_multiplier}"
              f"{'  [COLLAPSED]' if ctx.liquidity.is_collapsed else ''}")
        if ctx.event.type.value != "NONE":
            print(f"  EVENT       : {ctx.event.type.value} - {ctx.event.description}")

        audit.record("regime", tick=ctx.tick, micro=ctx.micro_regime.value,
                     vol=ctx.vol_regime.value, spread=ctx.spread, depth=ctx.liquidity.depth)

        fs = features.extract(game, market)
        signals = [s.evaluate(fs, regime=ctx.micro_regime) for s in strategies]

        opportunities = brain.evaluate_opportunities(signals, strat_map, ctx.micro_regime)
        print(f"  SIGNALS ({len(signals)}):")
        for s in signals:
            marker = "*" if s.is_actionable() else " "
            print(f"    [{marker}] {s.strategy_name:<22} {s.direction.value:<5} "
                  f"edge={s.edge:+.1f}  conf={s.confidence:.2f}")

        intents = router.allocate(signals, strat_map, ctx.micro_regime, portfolio)
        print(f"  ROUTER      : {len(intents)} intent(s) allocated "
              f"(of {len(opportunities)} ranked opportunities)")

        for intent in intents:
            slip = slippage.estimate(intent.price, intent.size, ctx.liquidity.depth, ctx.vol_regime)
            approved, reason = risk.evaluate(
                intent, spread=ctx.spread, regime=ctx.micro_regime,
                liquidity_depth=ctx.liquidity.depth, expected_slippage=slip.slippage_cents,
            )
            audit.record("risk", intent_id=intent.intent_id, approved=approved, reason=reason)
            if not approved:
                print(f"    VETO   {intent.strategy_name:<20} {intent.side.value} "
                      f"{intent.size}x @ {intent.price:.1f}c - {reason}")
                continue

            result = fill_engine.submit(intent)
            n_fills += 1
            trade = Trade(
                market_id=intent.market_id, strategy_name=intent.strategy_name,
                side=intent.side, price=result.filled_price or intent.price,
                size=result.filled_size or 0, fee=result.fee,
            )
            pnl.record(trade, requested_price=intent.price)
            exposure.add(intent.market_id, intent.strategy_name, intent.side,
                         trade.price, trade.size)
            risk.state.add_exposure(intent.strategy_name, trade.price * trade.size / 100.0)
            print(f"    FILL   {intent.strategy_name:<20} {intent.side.value} "
                  f"{result.filled_size}x @ {result.filled_price:.1f}c  [{result.message}]")
            audit.record("fill", intent_id=intent.intent_id, price=result.filled_price,
                         size=result.filled_size, msg=result.message)

        marks = {market.market_id: market.mid}
        equity = pnl.total_pnl(marks)
        perf.record_equity(equity)
        perf.record_regime_pnl(ctx.micro_regime.value, equity - prev_equity)
        prev_equity = equity
        risk.state.update_equity(equity)

        snapshots.capture(TickSnapshot(
            tick=ctx.tick, game_id=game.game_id, regime=ctx.micro_regime.value,
            mid_price=market.mid, spread=market.spread,
            liquidity_depth=ctx.liquidity.depth, n_signals=len(signals),
            n_fills=len(intents), pnl=round(equity, 2),
        ))
        reasoning = brain.summarize_reasoning(ctx.micro_regime, opportunities, len(intents))
        print(f"  PNL         : equity={equity:+.2f}  drawdown={risk.state.max_drawdown_seen:.2f}")
        print(f"  BRAIN       : {reasoning}")
        print()

    _print_analytics(scenario, pnl, exposure, perf, snapshots, n_fills, marks)
    print(DIVIDER + "\n  AUDIT LOG (last 10 events)\n" + DIVIDER)
    for e in audit.entries()[-10:]:
        print(f"  [{e.event_type}] {e.data}")
    print(f"\nReplay complete. {len(ticks)} tick(s) processed.\n")


# ---------------------------------------------------------------------------
# Bundle path (historical-style replay from a normalized data bundle).
# ---------------------------------------------------------------------------
def _run_bundle(bundle_path: str) -> None:
    from src.data.bundle import load_bundle, to_engine_ticks
    from src.data.timestamp import parse_timestamp, AmbiguousTimestampError

    bundle = load_bundle(bundle_path)
    engine_ticks = to_engine_ticks(bundle)

    strategies = _make_strategies()
    strat_map: Dict[str, object] = {s.NAME: s for s in strategies}

    features = FeatureExtractor()
    registry = ToolRegistry()
    brain = LocalBrain(registry)
    router = PortfolioRouter(max_concurrent_strategies=3, cooldown_ticks=1)
    risk = RiskManager(RiskConfig(max_drawdown=300.0, min_liquidity_depth=20, max_slippage_cents=15.0))
    fill_engine = FillEngine()
    slippage = SlippageModel()
    classifier = RegimeClassifier()
    audit = AuditLog()

    pnl = PnLTracker()
    exposure = ExposureTracker()
    perf = PerformanceAnalyzer()
    snapshots = SnapshotStore()
    portfolio = PortfolioState()

    verdict = bundle.quality_report.verdict.value if bundle.quality_report else "UNKNOWN"
    print(f"\n{DIVIDER}\n  BOOKIE HISTORICAL REPLAY  -  bundle={bundle.bundle_id}\n{DIVIDER}")
    print(f"  event={bundle.event_id} ({bundle.sport}/{bundle.league})  "
          f"ticks={len(engine_ticks)}  data_verdict={verdict}\n")

    n_fills = 0
    prev_equity = 0.0
    prev_mid = None
    prev_ts = None
    marks: Dict[str, float] = {}

    for i, (game, markets) in enumerate(engine_ticks, 1):
        market = markets[0]
        canonical_tick = bundle.ticks[i - 1]
        depth = max(1, market.open_interest)

        # Derive odds velocity from consecutive mids / timestamps.
        try:
            ts = parse_timestamp(canonical_tick.timestamp).timestamp()
        except (AmbiguousTimestampError, ValueError):
            ts = None
        if prev_mid is not None and prev_ts is not None and ts is not None and ts > prev_ts:
            odds_velocity = (market.mid - prev_mid) / (ts - prev_ts)
        else:
            odds_velocity = 0.0

        regime = classifier.classify(RegimeInputs(
            spread=market.spread,
            odds_velocity=odds_velocity,
            liquidity_depth=depth,
            volatility=abs(odds_velocity) * 60.0,
            time_remaining=game.clock_seconds,
            score_diff=game.score_diff,
            order_flow_imbalance=max(-1.0, min(1.0, odds_velocity * 10.0)),
            mid_price=market.mid,
        ))
        fill_engine.current_regime = VolatilityRegime.CALM
        fill_engine.book_depth = max(5, int(depth * 0.2))

        stale = canonical_tick.metadata.get("stale_market") or canonical_tick.metadata.get("stale_game")
        print(f"--- TICK {i} ---")
        print(f"  GAME STATE  : {game.home_team} {game.home_score} vs "
              f"{game.away_team} {game.away_score}  [{game.phase.value}]  "
              f"clock={game.clock_seconds}s  diff={game.score_diff:+d}")
        print(f"  MARKET STATE: {market.market_id}  mid={market.mid:.1f}c  "
              f"spread={market.spread:.1f}c  oi={market.open_interest}  vol={market.volume}")
        print(f"  REGIME      : {regime.value}  odds_velocity={odds_velocity:+.4f}c/s"
              f"{'  [STALE DATA]' if stale else ''}")

        audit.record("regime", tick=i, micro=regime.value, spread=market.spread, depth=depth)

        fs = features.extract(game, market)
        signals = [s.evaluate(fs, regime=regime) for s in strategies]
        opportunities = brain.evaluate_opportunities(signals, strat_map, regime)
        print(f"  SIGNALS ({len(signals)}):")
        for s in signals:
            marker = "*" if s.is_actionable() else " "
            print(f"    [{marker}] {s.strategy_name:<22} {s.direction.value:<5} "
                  f"edge={s.edge:+.1f}  conf={s.confidence:.2f}")

        intents = router.allocate(signals, strat_map, regime, portfolio)
        print(f"  ROUTER      : {len(intents)} intent(s) allocated "
              f"(of {len(opportunities)} ranked opportunities)")

        for intent in intents:
            slip = slippage.estimate(intent.price, intent.size, depth, fill_engine.current_regime)
            approved, reason = risk.evaluate(
                intent, spread=market.spread, regime=regime,
                liquidity_depth=depth, expected_slippage=slip.slippage_cents,
            )
            audit.record("risk", intent_id=intent.intent_id, approved=approved, reason=reason)
            if not approved:
                print(f"    VETO   {intent.strategy_name:<20} {intent.side.value} "
                      f"{intent.size}x @ {intent.price:.1f}c - {reason}")
                continue
            result = fill_engine.submit(intent)
            n_fills += 1
            trade = Trade(
                market_id=intent.market_id, strategy_name=intent.strategy_name,
                side=intent.side, price=result.filled_price or intent.price,
                size=result.filled_size or 0, fee=result.fee,
            )
            pnl.record(trade, requested_price=intent.price)
            exposure.add(intent.market_id, intent.strategy_name, intent.side, trade.price, trade.size)
            risk.state.add_exposure(intent.strategy_name, trade.price * trade.size / 100.0)
            print(f"    FILL   {intent.strategy_name:<20} {intent.side.value} "
                  f"{result.filled_size}x @ {result.filled_price:.1f}c  [{result.message}]")
            audit.record("fill", intent_id=intent.intent_id, price=result.filled_price, size=result.filled_size)

        marks = {market.market_id: market.mid}
        equity = pnl.total_pnl(marks)
        perf.record_equity(equity)
        perf.record_regime_pnl(regime.value, equity - prev_equity)
        prev_equity, prev_mid, prev_ts = equity, market.mid, ts
        risk.state.update_equity(equity)

        snapshots.capture(TickSnapshot(
            tick=i, game_id=game.game_id, regime=regime.value,
            mid_price=market.mid, spread=market.spread, liquidity_depth=depth,
            n_signals=len(signals), n_fills=len(intents), pnl=round(equity, 2),
        ))
        print(f"  PNL         : equity={equity:+.2f}  drawdown={risk.state.max_drawdown_seen:.2f}")
        print()

    _print_analytics(f"bundle:{bundle.bundle_id}", pnl, exposure, perf, snapshots, n_fills, marks)
    print(f"Historical replay complete. {len(engine_ticks)} tick(s) processed.")
    print("NOTE: historical replay is NOT proof of live edge — see docs/HISTORICAL_REPLAY.md.\n")


def _print_analytics(scenario, pnl, exposure, perf, snapshots, n_fills, marks) -> None:
    report = perf.build_report(
        realized=pnl.realized_total,
        unrealized=pnl.unrealized(marks),
        fees=pnl.fees_total,
        slippage_loss=pnl.slippage_loss,
        n_trades=n_fills,
    )
    print(DIVIDER + "\n  ANALYTICS\n" + DIVIDER)
    print(f"  total PnL        : {report.total_pnl:+.2f}c")
    print(f"  realized         : {report.realized_pnl:+.2f}c")
    print(f"  unrealized       : {report.unrealized_pnl:+.2f}c")
    print(f"  fees             : {report.fees:.2f}c")
    print(f"  slippage loss    : {report.slippage_loss:.2f}c")
    print(f"  sharpe-like       : {report.sharpe_like}")
    print(f"  max drawdown     : {report.max_drawdown:.2f}c ({report.max_drawdown_pct}%)")
    print(f"  fills            : {n_fills}")
    print(f"  exposure (total) : ${exposure.total():.2f}  concentration={exposure.concentration()}")
    print(f"  regime PnL       : {report.regime_pnl}")
    print(f"  exposure heatmap : {exposure.heatmap()}")
    print()


def run(scenario: str = "comeback", seed: int = 42, bundle: str | None = None) -> None:
    if bundle is not None:
        _run_bundle(bundle)
    elif scenario in SCRIPTED:
        _run_scripted(scenario)
    else:
        _run_simulated(scenario, seed=seed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bookie replay simulator")
    parser.add_argument(
        "--scenario", default="comeback",
        choices=["comeback", "blowout", "calm", "panic", "liquidity_crisis", "endgame_chaos"],
        help="Replay scenario to run",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for simulated scenarios")
    parser.add_argument("--bundle", default=None,
                        help="Path to a replay bundle JSON/JSONL (overrides --scenario)")
    args = parser.parse_args()
    run(scenario=args.scenario, seed=args.seed, bundle=args.bundle)


if __name__ == "__main__":
    main()
