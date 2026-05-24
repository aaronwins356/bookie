from __future__ import annotations

"""
Batch backtesting. Runs many configs, continues past individual failures
(recording them as warnings), aggregates results, builds a leaderboard, and
exports machine-readable artifacts.

Exports written to the output dir:
    batch_result.json     full BatchBacktestResult
    leaderboard.csv       ranked strategy rows
    strategy_metrics.csv  per-strategy-per-run metrics
    regime_metrics.csv    per-regime-per-run metrics
    warnings.txt          all warnings (per-run + batch-level)
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from src.backtest.config import BacktestConfig
from src.backtest.result import BatchBacktestResult, BacktestResult
from src.backtest.runner import BacktestRunner
from src.backtest.leaderboard import build_leaderboard
from src.backtest import significance, robustness


class BatchRunner:
    def __init__(self, compute_robustness: bool = True) -> None:
        self.runner = BacktestRunner()
        self.compute_robustness = compute_robustness

    def run(self, configs: List[BacktestConfig], batch_id: str = "batch") -> BatchBacktestResult:
        batch = BatchBacktestResult(batch_id=batch_id, configs=list(configs))

        for cfg in configs:
            try:
                result = self.runner.run(cfg)
            except Exception as exc:  # noqa: BLE001 - keep batch alive
                batch.warnings.append(f"RUN_FAILED [{cfg.name}] {type(exc).__name__}: {exc}")
                continue
            if result.warnings:
                # surface load-time / tick warnings from inside the run too
                for w in result.warnings:
                    batch.warnings.append(f"[{cfg.name}] {w}")
            result.warnings.extend(significance.evaluate_result_warnings(result, n_events=1))
            batch.results.append(result)

        if not batch.results:
            batch.warnings.append("BATCH_EMPTY: no successful runs")
            return batch

        robustness_scores = self._robustness_scores(configs)
        batch.leaderboard = build_leaderboard(batch.results, robustness_scores)
        batch.aggregate_metrics = self._aggregate(batch.results)
        batch.warnings.extend(self._batch_warnings(batch))
        return batch

    def _robustness_scores(self, configs: List[BacktestConfig]) -> Dict[str, float]:
        if not self.compute_robustness or not configs:
            return {}
        rep = configs[0]
        scores: Dict[str, float] = {}
        for name in rep.active_strategies():
            try:
                rep_report = robustness.strategy_robustness(name, rep, runner=self.runner)
                scores[name] = rep_report.score
            except Exception:  # noqa: BLE001
                scores[name] = 0.0
        return scores

    def _aggregate(self, results: List[BacktestResult]) -> Dict[str, object]:
        total_pnl = sum(r.pnl_summary.total_pnl_cents for r in results)
        total_fills = sum(r.fills for r in results)
        total_trades = sum(r.trades for r in results)
        total_rejected = sum(r.rejected_orders for r in results)
        worst_dd = max((r.drawdown_summary.max_drawdown_cents for r in results), default=0.0)
        return {
            "n_runs": len(results),
            "total_pnl_cents": round(total_pnl, 2),
            "avg_pnl_cents": round(total_pnl / len(results), 2),
            "total_trades": total_trades,
            "total_fills": total_fills,
            "total_rejected": total_rejected,
            "worst_run_drawdown_cents": round(worst_dd, 2),
        }

    def _batch_warnings(self, batch: BatchBacktestResult) -> List[str]:
        w: List[str] = []
        tf = significance.warn_too_few_events(len(batch.results))
        if tf:
            w.append(tf)
        return w


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def export_batch(batch: BatchBacktestResult, out_dir: str | Path) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, str] = {}

    json_path = out / "batch_result.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(batch.to_dict(), fh, indent=2, sort_keys=True)
    artifacts["batch_result"] = str(json_path)

    lb_path = out / "leaderboard.csv"
    with lb_path.open("w", encoding="utf-8", newline="") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["rank", "strategy", "score", "total_pnl_cents", "fills", "win_rate",
                       "sharpe_like", "max_drawdown_cents", "ev_capture", "robustness_score",
                       "warning_flags"])
        for rank, row in enumerate(batch.leaderboard, 1):
            wcsv.writerow([rank, row.strategy_name, row.score, row.total_pnl_cents, row.fills,
                           row.win_rate, row.sharpe_like, row.max_drawdown_cents, row.ev_capture,
                           row.robustness_score, "|".join(row.warning_flags)])
    artifacts["leaderboard_csv"] = str(lb_path)

    sm_path = out / "strategy_metrics.csv"
    with sm_path.open("w", encoding="utf-8", newline="") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["run", "strategy", "trades", "fills", "wins", "losses",
                       "total_pnl_cents", "win_rate", "avg_pnl_cents", "ev_capture"])
        for res in batch.results:
            for m in res.strategy_metrics:
                wcsv.writerow([res.config.name, m.strategy_name, m.trades, m.fills, m.wins,
                               m.losses, m.total_pnl_cents, m.win_rate, m.avg_pnl_cents, m.ev_capture])
    artifacts["strategy_metrics_csv"] = str(sm_path)

    rm_path = out / "regime_metrics.csv"
    with rm_path.open("w", encoding="utf-8", newline="") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["run", "regime", "ticks", "fills", "pnl_cents"])
        for res in batch.results:
            for r in res.regime_metrics:
                wcsv.writerow([res.config.name, r.regime, r.ticks, r.fills, r.pnl_cents])
    artifacts["regime_metrics_csv"] = str(rm_path)

    warn_path = out / "warnings.txt"
    with warn_path.open("w", encoding="utf-8") as fh:
        if batch.warnings:
            fh.write("== BATCH WARNINGS ==\n")
            for x in batch.warnings:
                fh.write(x + "\n")
        for res in batch.results:
            if res.warnings:
                fh.write(f"\n== {res.config.name} ==\n")
                for x in res.warnings:
                    fh.write(x + "\n")
    artifacts["warnings_txt"] = str(warn_path)

    return artifacts
