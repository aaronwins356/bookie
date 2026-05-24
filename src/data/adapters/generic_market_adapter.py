from __future__ import annotations

"""
Generic market adapter. Loads market-snapshot rows from a CSV or JSON file
(dispatched by extension) and normalizes them into CanonicalMarketSnapshot.

Source-agnostic: relies on the normalizer's field aliases. Provider-specific
adapters can pre-map fields before normalization.
"""

from pathlib import Path
from typing import List

from src.data.adapters.csv_adapter import read_csv
from src.data.adapters.json_adapter import read_json
from src.data.normalizer import normalize_markets
from src.data.schemas import CanonicalMarketSnapshot


def load_markets(path: str | Path) -> List[CanonicalMarketSnapshot]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        rows = read_csv(p)
    elif ext == ".json":
        rows = read_json(p)
    elif ext == ".jsonl":
        rows = _read_jsonl(p)
    else:
        raise ValueError(f"unsupported market file extension: {ext}")
    return normalize_markets(rows)


def _read_jsonl(path: Path):
    import json
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
