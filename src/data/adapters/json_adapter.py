from __future__ import annotations

"""
JSON adapter — reads a JSON file into a list of raw dict rows.

Accepts three shapes:
- a top-level list of objects
- a single object (wrapped into a one-element list)
- an object with a "rows" / "data" / "records" key holding the list
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def read_json(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if isinstance(payload, list):
        return [dict(r) for r in payload]

    if isinstance(payload, dict):
        for key in ("rows", "data", "records"):
            if key in payload and isinstance(payload[key], list):
                return [dict(r) for r in payload[key]]
        return [dict(payload)]

    raise ValueError(f"unsupported JSON structure in {p}")
