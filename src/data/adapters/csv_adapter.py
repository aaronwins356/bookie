from __future__ import annotations

"""CSV adapter — reads a CSV file into a list of raw dict rows."""

import csv
from pathlib import Path
from typing import Any, Dict, List


def read_csv(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]
