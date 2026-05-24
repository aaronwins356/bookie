from __future__ import annotations

"""
Snapshot store. Captures a per-tick snapshot of the full observable state
(game, market, regime, liquidity, signals, fills, pnl) for later analysis
and reproducible replay.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TickSnapshot:
    tick: int
    game_id: str
    regime: str
    mid_price: float
    spread: float
    liquidity_depth: int
    n_signals: int
    n_fills: int
    pnl: float
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotStore:
    path: Optional[Path] = None
    snapshots: List[TickSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def capture(self, snap: TickSnapshot) -> None:
        self.snapshots.append(snap)

    def flush(self) -> None:
        if self.path is None:
            return
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump([asdict(s) for s in self.snapshots], fh, indent=2)

    def latest(self) -> Optional[TickSnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    def pnl_series(self) -> List[float]:
        return [s.pnl for s in self.snapshots]
