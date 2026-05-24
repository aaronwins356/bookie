from __future__ import annotations

"""
Backtest configuration.

A BacktestConfig fully specifies one run: where the data comes from
(scenario or bundle), the cost/latency assumptions, which strategies are
enabled, and where to write artifacts. Configs are plain dataclasses with
JSON ser/de so they can be persisted alongside results and reproduced.

Cost knobs map onto existing engine components:
- fee_cents_per_contract -> FillEngine.fee_per_contract
- slippage_impact        -> SlippageModel(impact_coeff=...)
- latency_ms             -> LatencyModel(base_ms=...)
- max_positions          -> PortfolioRouter(max_concurrent_strategies=...)
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# Default cost assumptions (match the engine's own defaults).
DEFAULT_FEE = 0.01
DEFAULT_SLIPPAGE_IMPACT = 4.0
DEFAULT_LATENCY_MS = 80.0

ALL_STRATEGIES = [
    "favorite_grinder", "endgame_bonding", "momentum",
    "overpriced_fade", "liquidity_vacuum",
]
SCENARIOS = ["calm", "panic", "liquidity_crisis", "endgame_chaos", "comeback", "blowout"]


@dataclass
class BacktestConfig:
    name: str
    seed: int = 1
    starting_bankroll_cents: float = 100_000.0
    fee_cents_per_contract: float = DEFAULT_FEE
    slippage_impact: float = DEFAULT_SLIPPAGE_IMPACT
    latency_ms: float = DEFAULT_LATENCY_MS
    max_positions: int = 3
    enabled_strategies: List[str] = field(default_factory=lambda: list(ALL_STRATEGIES))
    disabled_strategies: List[str] = field(default_factory=list)
    scenario_name: Optional[str] = None
    bundle_path: Optional[str] = None
    output_dir: Optional[str] = None
    notes: str = ""

    def active_strategies(self) -> List[str]:
        disabled = set(self.disabled_strategies)
        return [s for s in self.enabled_strategies if s not in disabled]

    def source_label(self) -> str:
        if self.bundle_path:
            return f"bundle:{self.bundle_path}"
        if self.scenario_name:
            return f"scenario:{self.scenario_name}"
        return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BacktestConfig":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)  # type: ignore[arg-type]
