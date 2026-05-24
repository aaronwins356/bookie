from __future__ import annotations

"""
Persistent audit store. Appends audit events to a JSONL file (one JSON
object per line) so a replay can be reconstructed and reviewed offline.
In-memory only until `path` is provided.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuditStore:
    path: Optional[Path] = None
    buffer: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, **data: Any) -> Dict[str, Any]:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        self.buffer.append(record)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        return record

    def load(self) -> List[Dict[str, Any]]:
        if self.path is None or not self.path.exists():
            return list(self.buffer)
        out: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def count(self, event_type: Optional[str] = None) -> int:
        if event_type is None:
            return len(self.buffer)
        return sum(1 for r in self.buffer if r["event_type"] == event_type)
