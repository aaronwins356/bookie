from __future__ import annotations

"""
Robustness testing. Reruns a config under harsher assumptions and across
seeds, then scores how well performance survives. A strategy that only
works with zero slippage, one seed, no latency, or one regime/event should
score poorly - that is the point.

Note on perturbations: spreads and book liquidity originate in the scenario
engine / data and are not direct config knobs, so "wider spreads" and "lower
liquidity" are stressed via the slippage-impact channel (higher impact
coefficient = more costly fills against a thinner effective book). This is
documented in docs/RESEARCH_WARNINGS.md.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List

from src.backtest.config import BacktestConfig
from src.backtest.runner import BacktestRunner


@dataclass
class RobustnessReport:
    base_pnl: float
    perturbation_pnls: Dict[str, float] = field(default_factory=dict)
    seed_pnls: List[float] = field(default_factory=list)
    score: float = 0.0
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "base_pnl": round(self.base_pnl, 2),
            "perturbation_pnls": {k: round(v, 2) for k, v in self.perturbation_pnls.items()},
            "seed_pnls": [round(x, 2) for x in self.seed_pnls],
            "score": round(self.score, 3),
            "flags": self.flags,
        }


def _stdev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def _perturbations(base: BacktestConfig) -> Dict[str, BacktestConfig]:
    return {
        "worse_slippage": replace(base, slippage_impact=base.slippage_impact * 3.0 + 4.0),
        "higher_latency": replace(base, latency_ms=base.latency_ms * 3.0 + 100.0),
        "higher_fees": replace(base, fee_cents_per_contract=base.fee_cents_per_contract * 10.0 + 0.5),
        "thin_liquidity": replace(base, slippage_impact=base.slippage_impact * 5.0 + 8.0),
    }


def run_robustness(
    base_config: BacktestConfig,
    seeds: List[int] | None = None,
    runner: BacktestRunner | None = None,
) -> RobustnessReport:
    runner = runner or BacktestRunner()
    seeds = seeds or [base_config.seed, base_config.seed + 1, base_config.seed + 2]

    base = runner.run(base_config)
    base_pnl = base.pnl_summary.total_pnl_cents
    report = RobustnessReport(base_pnl=base_pnl)

    for name, cfg in _perturbations(base_config).items():
        report.perturbation_pnls[name] = runner.run(cfg).pnl_summary.total_pnl_cents

    for s in seeds:
        report.seed_pnls.append(runner.run(replace(base_config, seed=s)).pnl_summary.total_pnl_cents)

    report.score = _score(report)
    report.flags = _flags(report)
    return report


def _score(report: RobustnessReport) -> float:
    runs = [report.base_pnl] + list(report.perturbation_pnls.values())
    if not runs:
        return 0.0
    positive_fraction = sum(1 for p in runs if p > 0) / len(runs)

    seeds = report.seed_pnls
    if len(seeds) >= 2:
        mean = sum(seeds) / len(seeds)
        sd = _stdev(seeds)
        seed_stability = 1.0 - min(1.0, sd / (abs(mean) + 1.0))
        seed_positive = sum(1 for p in seeds if p > 0) / len(seeds)
    else:
        seed_stability = 0.5
        seed_positive = 1.0 if (seeds and seeds[0] > 0) else 0.0

    score = 0.4 * positive_fraction + 0.3 * seed_stability + 0.3 * seed_positive
    return round(max(0.0, min(1.0, score)), 3)


def _flags(report: RobustnessReport) -> List[str]:
    flags: List[str] = []
    if report.base_pnl > 0:
        for name, pnl in report.perturbation_pnls.items():
            if pnl <= 0:
                flags.append(f"COLLAPSES_UNDER_{name.upper()}")
    seeds = report.seed_pnls
    if len(seeds) >= 2:
        positive = sum(1 for p in seeds if p > 0)
        if positive == 1 and report.base_pnl > 0:
            flags.append("SINGLE_SEED_DEPENDENT")
    return flags


def strategy_robustness(strategy_name: str, base_config: BacktestConfig,
                        runner: BacktestRunner | None = None) -> RobustnessReport:
    """Robustness of a single strategy in isolation under the same source."""
    solo = replace(base_config, enabled_strategies=[strategy_name], disabled_strategies=[])
    return run_robustness(solo, runner=runner)
