from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class AuditEntry:
    timestamp: str
    event_type: str
    data: Dict[str, Any]


class AuditLog:
    """Append-only in-memory audit trail for the replay simulator."""

    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def record(self, event_type: str, **kwargs: Any) -> None:
        self._entries.append(
            AuditEntry(
                timestamp=datetime.utcnow().isoformat(),
                event_type=event_type,
                data=dict(kwargs),
            )
        )

    def entries(self) -> List[AuditEntry]:
        return list(self._entries)

    def dump(self) -> None:
        for e in self._entries:
            print(f"[{e.timestamp}] {e.event_type}: {e.data}")
