from __future__ import annotations

"""
Significance & fake-edge detection.

These tools are intentionally *conservative*: with tiny samples we cannot
prove anything, so the job here is to raise honest warnings, not to claim
statistical certainty. Every helper is deterministic given a seed.
"""

import random
from dataclasses import dataclass
from typing import List, Optional

from src.backtest.result import BacktestResult

# Thresholds (deliberately blunt).
MIN_FILLS = 30                 # below this, results are anecdotal
MIN_EVENTS = 5                 # below this, no cross-event generalization
HIGH_VARIANCE_RATIO = 2.0      # stdev/|mean| above this = noisy
LAGGING_MID_EDGE = 12.0        # mean abs edge above this is suspicious
CONCENTRATION_PCT = 0.8        # one regime/event driving >80% of PnL


@dataclass
class ConfidenceInterval:
    mean: float
    low: float
    high: float
    n: int
    confidence: float

    @property
    def crosses_zero(self) -> bool:
        return self.low <= 0.0 <= self.high


def bootstrap_ci(
    samples: List[float],
    confidence: float = 0.9,
    iterations: int = 2000,
    seed: int = 1,
) -> ConfidenceInterval:
    """Percentile bootstrap CI for the mean. Deterministic with `seed`."""
    n = len(samples)
    if n == 0:
        return ConfidenceInterval(0.0, 0.0, 0.0, 0, confidence)
    if n == 1:
        return ConfidenceInterval(samples[0], samples[0], samples[0], 1, confidence)

    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        resample = [samples[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = means[int(alpha * iterations)]
    hi = means[min(iterations - 1, int((1.0 - alpha) * iterations))]
    mean = sum(samples) / n
    return ConfidenceInterval(round(mean, 4), round(lo, 4), round(hi, 4), n, confidence)


def _stdev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def warn_low_sample(fills: int) -> Optional[str]:
    if fills < MIN_FILLS:
        return f"LOW_SAMPLE: only {fills} fills (< {MIN_FILLS}); results are anecdotal"
    return None


def warn_too_few_events(n_events: int) -> Optional[str]:
    if n_events < MIN_EVENTS:
        return f"TOO_FEW_EVENTS: {n_events} event(s) (< {MIN_EVENTS}); cannot generalize"
    return None


def warn_high_variance(fill_pnls: List[float]) -> Optional[str]:
    if len(fill_pnls) < 2:
        return None
    mean = sum(fill_pnls) / len(fill_pnls)
    sd = _stdev(fill_pnls)
    if abs(mean) < 1e-9:
        return "HIGH_VARIANCE: mean PnL ~0 with nonzero dispersion"
    if sd / abs(mean) > HIGH_VARIANCE_RATIO:
        return f"HIGH_VARIANCE: stdev/|mean| = {sd/abs(mean):.1f} (> {HIGH_VARIANCE_RATIO})"
    return None


def warn_perfect_winrate(win_rate: float, fills: int) -> Optional[str]:
    if fills >= 3 and win_rate >= 0.999:
        return f"PERFECT_WINRATE: {fills} fills all winners; almost certainly an artifact"
    return None


def warn_lagging_mid(avg_abs_edge: float, win_rate: float) -> Optional[str]:
    if avg_abs_edge >= LAGGING_MID_EDGE and win_rate >= 0.7:
        return (f"LAGGING_MID_ARTIFACT: avg edge {avg_abs_edge:.1f}c with win rate "
                f"{win_rate:.0%}; edge may just be a slow-to-reprice mid, not real")
    return None


def warn_concentration(pnl_by_bucket: dict, label: str) -> Optional[str]:
    total = sum(abs(v) for v in pnl_by_bucket.values())
    if total <= 0:
        return None
    top = max(pnl_by_bucket.values(), key=abs, default=0.0)
    if abs(top) / total >= CONCENTRATION_PCT:
        return (f"{label}_CONCENTRATION: a single {label.lower()} drives "
                f"{abs(top)/total:.0%} of PnL; result is fragile")
    return None


def evaluate_result_warnings(result: BacktestResult, n_events: int = 1) -> List[str]:
    """Aggregate conservative warnings for a single backtest result."""
    warnings: List[str] = []
    for w in (
        warn_low_sample(result.fills),
        warn_too_few_events(n_events),
        warn_high_variance(result.fill_pnls),
    ):
        if w:
            warnings.append(w)

    # Per-strategy edge/winrate artifact checks.
    for m in result.strategy_metrics:
        if m.fills == 0:
            continue
        for w in (
            warn_perfect_winrate(m.win_rate, m.fills),
            warn_lagging_mid(abs(m.avg_edge), m.win_rate),
        ):
            if w:
                warnings.append(f"[{m.strategy_name}] {w}")

    # Regime concentration over the whole run.
    regime_pnl = {r.regime: r.pnl_cents for r in result.regime_metrics}
    rc = warn_concentration(regime_pnl, "REGIME")
    if rc:
        warnings.append(rc)

    return warnings
