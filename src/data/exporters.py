from __future__ import annotations

"""
Exporters. File IO for replay bundles in JSON (single object) and JSONL
(one tick per line, with a header line) formats. Deterministic: keys are
sorted and ordering is preserved so re-exporting identical data yields
byte-identical files.
"""

import json
from pathlib import Path
from typing import Any, Dict

from src.data.schemas import ReplayBundle


def write_json(bundle: ReplayBundle, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(bundle.to_dict(), fh, indent=2, sort_keys=True)


def read_json(path: str | Path) -> ReplayBundle:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        return ReplayBundle.from_dict(json.load(fh))


def write_jsonl(bundle: ReplayBundle, path: str | Path) -> None:
    """
    JSONL layout: first line is a header object (bundle metadata + quality
    report, no ticks); each subsequent line is one tick.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header: Dict[str, Any] = {
        "_type": "bundle_header",
        "bundle_id": bundle.bundle_id,
        "created_at": bundle.created_at,
        "sport": bundle.sport,
        "league": bundle.league,
        "event_id": bundle.event_id,
        "quality_report": bundle.quality_report.to_dict() if bundle.quality_report else None,
        "source_metadata": bundle.source_metadata,
    }
    with p.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for tick in bundle.ticks:
            fh.write(json.dumps(tick.to_dict(), sort_keys=True) + "\n")


def read_jsonl(path: str | Path) -> ReplayBundle:
    from src.data.schemas import CanonicalReplayTick, DataQualityReport
    p = Path(path)
    header = None
    ticks = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("_type") == "bundle_header":
                header = obj
            else:
                ticks.append(CanonicalReplayTick.from_dict(obj))
    if header is None:
        raise ValueError(f"no bundle header line found in {p}")
    qr = header.get("quality_report")
    return ReplayBundle(
        bundle_id=header["bundle_id"],
        created_at=header["created_at"],
        sport=header["sport"],
        league=header["league"],
        event_id=header["event_id"],
        ticks=ticks,
        quality_report=DataQualityReport.from_dict(qr) if qr else None,
        source_metadata=header.get("source_metadata", {}),
    )
