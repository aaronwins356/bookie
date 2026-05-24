from __future__ import annotations

"""
Generic sports adapter. Loads game-event rows from a CSV or JSON file
(dispatched by extension) and normalizes them into CanonicalGameEvent.

"Generic" = source-agnostic: it relies on the normalizer's field aliases
rather than any one provider's schema. Provider-specific adapters can be
added later by pre-mapping their fields before handing rows to the
normalizer.
"""

from pathlib import Path
from typing import List

from src.data.adapters.csv_adapter import read_csv
from src.data.adapters.json_adapter import read_json
from src.data.normalizer import normalize_games
from src.data.schemas import CanonicalGameEvent


def load_games(path: str | Path) -> List[CanonicalGameEvent]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        rows = read_csv(p)
    elif ext in (".json", ".jsonl"):
        rows = read_json(p) if ext == ".json" else _read_jsonl(p)
    else:
        raise ValueError(f"unsupported game file extension: {ext}")
    return normalize_games(rows)


def _read_jsonl(path: Path):
    import json
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
