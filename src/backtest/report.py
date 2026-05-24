from __future__ import annotations

"""
Research report generation. Produces a plain-text report (report.txt) and a
machine-readable JSON for a batch result. The report is deliberately
honest: it leads with warnings and ends with a disclaimer that simulated /
historical performance is not proof of live edge.
"""

import json
from pathlib import Path
from typing import List

from src.backtest.result import BatchBacktestResult, BacktestResult

DISCLAIMER = (
    "DISCLAIMER: These results come from simulated scenarios and/or historical "
    "replay with FAKE fills. They are NOT proof of live edge. Do not size real "
    "capital from this. See docs/RESEARCH_WARNINGS.md and docs/HISTORICAL_REPLAY.md."
)


def _section(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}\n"


def build_report_text(batch: BatchBacktestResult) -> str:
    lines: List[str] = []
    lines.append(_section(f"BACKTEST RESEARCH REPORT - {batch.batch_id}"))

    agg = batch.aggregate_metrics
    lines.append("CONFIG SUMMARY")
    if batch.configs:
        c = batch.configs[0]
        lines.append(f"  runs              : {agg.get('n_runs', len(batch.results))}")
        lines.append(f"  sources           : {sorted({cfg.source_label() for cfg in batch.configs})}")
        lines.append(f"  seeds             : {sorted({cfg.seed for cfg in batch.configs})}")
        lines.append(f"  fee/slip/latency  : {c.fee_cents_per_contract} / "
                     f"{c.slippage_impact} / {c.latency_ms}ms")
    lines.append("")

    lines.append("AGGREGATE")
    for k, v in agg.items():
        lines.append(f"  {k:<24}: {v}")
    lines.append("")

    if batch.leaderboard:
        lines.append("LEADERBOARD (balanced score; not raw PnL)")
        lines.append(f"  {'rank':<5}{'strategy':<20}{'score':>8}{'pnl':>10}"
                     f"{'fills':>7}{'winr':>7}{'robust':>8}  flags")
        for rank, row in enumerate(batch.leaderboard, 1):
            lines.append(f"  {rank:<5}{row.strategy_name:<20}{row.score:>8.3f}"
                         f"{row.total_pnl_cents:>10.1f}{row.fills:>7}{row.win_rate:>7.2f}"
                         f"{row.robustness_score:>8.2f}  {','.join(row.warning_flags) or '-'}")
        best = batch.leaderboard[0]
        worst = batch.leaderboard[-1]
        lines.append("")
        lines.append(f"  best strategy : {best.strategy_name} (score {best.score:.3f})")
        lines.append(f"  worst strategy: {worst.strategy_name} (score {worst.score:.3f})")
    lines.append("")

    # Regime view aggregated across runs.
    regime_pnl: dict = {}
    regime_fills: dict = {}
    for res in batch.results:
        for r in res.regime_metrics:
            regime_pnl[r.regime] = regime_pnl.get(r.regime, 0.0) + r.pnl_cents
            regime_fills[r.regime] = regime_fills.get(r.regime, 0) + r.fills
    if regime_pnl:
        lines.append("REGIME PERFORMANCE (aggregate PnL)")
        ordered = sorted(regime_pnl.items(), key=lambda kv: -kv[1])
        for reg, pnl in ordered:
            lines.append(f"  {reg:<22} pnl={pnl:>10.1f}  fills={regime_fills.get(reg, 0)}")
        lines.append(f"  best regime  : {ordered[0][0]}")
        lines.append(f"  worst regime : {ordered[-1][0]}")
    lines.append("")

    worst_dd = agg.get("worst_run_drawdown_cents", 0.0)
    lines.append("DRAWDOWN NOTES")
    lines.append(f"  worst single-run drawdown: {worst_dd} cents")
    lines.append("")

    lines.append("FAKE-EDGE / RESEARCH WARNINGS")
    all_warnings = list(batch.warnings)
    for res in batch.results:
        all_warnings.extend(f"[{res.config.name}] {w}" for w in res.warnings)
    if all_warnings:
        for w in all_warnings[:40]:
            lines.append(f"  - {w}")
        if len(all_warnings) > 40:
            lines.append(f"  ... and {len(all_warnings) - 40} more")
    else:
        lines.append("  (none raised - but absence of warnings is NOT proof of edge)")
    lines.append("")

    lines.append("ROBUSTNESS NOTES")
    if batch.leaderboard:
        fragile = [r.strategy_name for r in batch.leaderboard if r.robustness_score < 0.4]
        sturdy = [r.strategy_name for r in batch.leaderboard if r.robustness_score >= 0.6]
        lines.append(f"  sturdier (>=0.6) : {sturdy or '(none)'}")
        lines.append(f"  fragile  (<0.4)  : {fragile or '(none)'}")
    lines.append("")

    lines.append("NEXT RECOMMENDED RESEARCH STEPS")
    lines.append("  1. Gather more independent events (current sample is tiny).")
    lines.append("  2. Use train/test or walk-forward splits (src.backtest.splits).")
    lines.append("  3. Re-run survivors under harsher robustness settings.")
    lines.append("  4. Replace fake fills with realistic execution before trusting PnL.")
    lines.append("")

    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


def write_report(batch: BatchBacktestResult, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / "report.txt"
    txt_path.write_text(build_report_text(batch), encoding="utf-8")
    json_path = out / "report.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump({
            "batch_id": batch.batch_id,
            "aggregate_metrics": batch.aggregate_metrics,
            "leaderboard": [r.to_dict() for r in batch.leaderboard],
            "warnings": batch.warnings,
            "disclaimer": DISCLAIMER,
        }, fh, indent=2, sort_keys=True)
    return {"report_txt": str(txt_path), "report_json": str(json_path)}
