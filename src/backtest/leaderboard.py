from __future__ import annotations

"""
Strategy leaderboard. Aggregates per-strategy metrics across many backtest
results and ranks strategies by a *balanced* score - not raw PnL - so that
high-PnL-but-fragile strategies do not top the board.

The score blends bounded terms (PnL, Sharpe-like, win rate, EV capture,
robustness) and subtracts penalties (drawdown, low sample, warning flags).
All terms are squashed with tanh so no single dimension dominates.
"""

import math
from typing import Dict, List, Optional

from src.backtest.result import BacktestResult, StrategyLeaderboardRow
from src.backtest import significance


def _drawdown(series: List[float]) -> float:
    """Max peak-to-trough drawdown over a cumulative sum of per-run PnLs."""
    peak = 0.0
    cum = 0.0
    max_dd = 0.0
    for x in series:
        cum += x
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return max_dd


def _sharpe_like(series: List[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return round(mean / sd * math.sqrt(n), 3)


class _Agg:
    def __init__(self, name: str) -> None:
        self.name = name
        self.trades = 0
        self.fills = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.edge_sum = 0.0
        self.slippage_loss = 0.0
        self.regime_pnl: Dict[str, float] = {}
        self.per_run_pnl: List[float] = []


def aggregate_strategies(results: List[BacktestResult]) -> Dict[str, _Agg]:
    aggs: Dict[str, _Agg] = {}
    for res in results:
        for m in res.strategy_metrics:
            a = aggs.setdefault(m.strategy_name, _Agg(m.strategy_name))
            a.trades += m.trades
            a.fills += m.fills
            a.wins += m.wins
            a.losses += m.losses
            a.total_pnl += m.total_pnl_cents
            a.edge_sum += m.edge_sum
            a.slippage_loss += m.slippage_loss_cents
            a.per_run_pnl.append(m.total_pnl_cents)
            for r, v in m.regime_pnl.items():
                a.regime_pnl[r] = a.regime_pnl.get(r, 0.0) + v
    return aggs


def _row_warnings(a: _Agg) -> List[str]:
    flags: List[str] = []
    win_rate = a.wins / (a.wins + a.losses) if (a.wins + a.losses) else 0.0
    avg_edge = a.edge_sum / a.trades if a.trades else 0.0
    for w in (
        significance.warn_low_sample(a.fills),
        significance.warn_perfect_winrate(win_rate, a.fills),
        significance.warn_lagging_mid(abs(avg_edge), win_rate),
        significance.warn_concentration(a.regime_pnl, "REGIME"),
    ):
        if w:
            # keep flags short (codes only)
            flags.append(w.split(":")[0].strip("[] "))
    return flags


def _balanced_score(row: StrategyLeaderboardRow, warning_count: int) -> float:
    pnl_term = math.tanh(row.total_pnl_cents / 500.0)
    sharpe_term = math.tanh(row.sharpe_like)
    winrate_term = (row.win_rate - 0.5) * 2.0
    ev_term = math.tanh(row.ev_capture)
    robustness_term = row.robustness_score            # already 0..1
    dd_penalty = math.tanh(row.max_drawdown_cents / 500.0)

    score = (
        0.30 * pnl_term
        + 0.20 * sharpe_term
        + 0.15 * winrate_term
        + 0.10 * ev_term
        + 0.25 * robustness_term
        - 0.20 * dd_penalty
    )
    score -= 0.1 * warning_count
    if row.fills < significance.MIN_FILLS:
        score *= 0.5          # low-sample haircut
    return round(score, 4)


def build_leaderboard(
    results: List[BacktestResult],
    robustness_scores: Optional[Dict[str, float]] = None,
) -> List[StrategyLeaderboardRow]:
    robustness_scores = robustness_scores or {}
    aggs = aggregate_strategies(results)
    rows: List[StrategyLeaderboardRow] = []

    for name, a in aggs.items():
        win_rate = round(a.wins / (a.wins + a.losses), 4) if (a.wins + a.losses) else 0.0
        avg_pnl = round(a.total_pnl / a.fills, 3) if a.fills else 0.0
        ev_capture = round(a.total_pnl / a.edge_sum, 3) if a.edge_sum else 0.0
        strengths = sorted([r for r, v in a.regime_pnl.items() if v > 0],
                           key=lambda r: -a.regime_pnl[r])
        weaknesses = sorted([r for r, v in a.regime_pnl.items() if v < 0],
                            key=lambda r: a.regime_pnl[r])

        row = StrategyLeaderboardRow(
            strategy_name=name,
            trades=a.trades,
            fills=a.fills,
            win_rate=win_rate,
            total_pnl_cents=round(a.total_pnl, 2),
            avg_pnl_cents=avg_pnl,
            max_drawdown_cents=round(_drawdown(a.per_run_pnl), 2),
            sharpe_like=_sharpe_like(a.per_run_pnl),
            expectancy=avg_pnl,                       # expected PnL per fill
            ev_capture=ev_capture,
            slippage_loss=round(a.slippage_loss, 2),
            regime_strengths=strengths[:3],
            regime_weaknesses=weaknesses[:3],
            robustness_score=round(robustness_scores.get(name, 0.0), 3),
            warning_flags=_row_warnings(a),
        )
        row.score = _balanced_score(row, len(row.warning_flags))
        rows.append(row)

    rows.sort(key=lambda r: -r.score)
    return rows
