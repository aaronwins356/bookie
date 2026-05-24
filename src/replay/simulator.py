from __future__ import annotations

"""
CLI replay simulator.

Usage:
    python -m src.replay.simulator
    python -m src.replay.simulator --scenario blowout
"""

import argparse
import sys

from src.replay.sample_data_loader import SampleDataLoader
from src.strategies import (
    FavoriteGrinder, EndgameBonding, MomentumStrategy,
    OverpricedFade, LiquidityVacuum,
)
from src.engine.router import Router
from src.engine.risk import RiskManager, RiskConfig
from src.engine.execution import ExecutionEngine
from src.engine.audit import AuditLog
from src.controller.tool_registry import ToolRegistry
from src.controller.local_brain import LocalBrain
from src.controller.decision_loop import DecisionLoop
from src.adapters.mock_execution_adapter import MockExecutionAdapter


DIVIDER = "=" * 60


def build_loop() -> DecisionLoop:
    strategies = [
        FavoriteGrinder(),
        EndgameBonding(),
        MomentumStrategy(),
        OverpricedFade(),
        LiquidityVacuum(),
    ]
    registry = ToolRegistry()
    brain = LocalBrain(registry)
    router = Router()
    risk = RiskManager(RiskConfig())
    execution = ExecutionEngine(MockExecutionAdapter())
    audit = AuditLog()

    return DecisionLoop(strategies, brain, router, risk, execution, audit)


def run(scenario: str = "comeback") -> None:
    loader = SampleDataLoader()
    if scenario == "blowout":
        ticks = loader.load_blowout()
    else:
        ticks = loader.load_nfl_comeback()

    loop = build_loop()

    print(f"\n{DIVIDER}")
    print(f"  BOOKIE REPLAY SIMULATOR  —  scenario={scenario}")
    print(f"{DIVIDER}\n")

    for i, (game, markets) in enumerate(ticks, 1):
        print(f"--- TICK {i} ---")
        print(f"  GAME STATE  : {game.home_team} {game.home_score} vs "
              f"{game.away_team} {game.away_score}  "
              f"[{game.phase.value}]  clock={game.clock_seconds}s  "
              f"diff={game.score_diff:+d}")

        for m in markets:
            print(f"  MARKET STATE: {m.market_id}  mid={m.mid:.1f}¢  "
                  f"spread={m.spread:.1f}¢  vol={m.volume}")

        signals, results = loop.tick(game, markets)

        print(f"  SIGNALS ({len(signals)}):")
        for s in signals:
            marker = "*" if s.is_actionable() else " "
            print(f"    [{marker}] {s.strategy_name:<22} {s.direction.value:<5} "
                  f"edge={s.edge:+.1f}  conf={s.confidence:.2f}  "
                  f"fair={s.fair_value:.1f}  notes={s.notes}")

        actionable = [s for s in signals if s.is_actionable()]
        print(f"  ROUTER      : {len(actionable)} actionable signal(s) routed")

        if results:
            print(f"  EXECUTIONS  : {len(results)} fill(s)")
            for r in results:
                print(f"    => {r.market_id} status={r.status.value} "
                      f"price={r.filled_price}¢ size={r.filled_size}")
        else:
            print("  EXECUTIONS  : none")

        print()

    print(DIVIDER)
    print("  AUDIT LOG")
    print(DIVIDER)
    loop.audit.dump()
    print(f"\nReplay complete. {len(ticks)} tick(s) processed.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bookie replay simulator")
    parser.add_argument(
        "--scenario",
        default="comeback",
        choices=["comeback", "blowout"],
        help="Replay scenario to run",
    )
    args = parser.parse_args()
    run(scenario=args.scenario)


if __name__ == "__main__":
    main()
