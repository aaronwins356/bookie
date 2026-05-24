# Data Pipeline (Phase 3)

Turns raw historical-style CSV/JSON files into validated, replay-ready
bundles. Local files only — no live APIs, no secrets.

## Flow

```
raw CSV/JSON
     │  adapters (csv_adapter / json_adapter)
     ▼
raw dict rows
     │  normalizer  (field-alias resolution, NO-side & liquidity derivation)
     ▼
CanonicalGameEvent[] + CanonicalMarketSnapshot[]
     │  validators  (structured ValidationIssue list)
     ▼
issues ──────────────┐
     │  aligner       │ (nearest-event join, lag/staleness, max-lag drop)
     ▼                │
CanonicalReplayTick[] │
     │  quality       │ (DataQualityReport: counts, gaps, verdict)
     ▼                ▼
        ReplayBundle  (ticks + quality_report + source_metadata)
     │  exporters (JSON / JSONL, deterministic)
     ▼
replay_bundle.json ──► replay simulator (--bundle)
```

## Module map (`src/data/`)

| Module          | Responsibility                                             |
|-----------------|------------------------------------------------------------|
| `schemas.py`    | Canonical models, `ValidationIssue`, `DataQualityReport`   |
| `timestamp.py`  | Parse ISO / unix-s / unix-ms → UTC; reject ambiguous       |
| `normalizer.py` | Messy field names → canonical models                       |
| `validators.py` | Structured data-quality checks                             |
| `aligner.py`    | Join market snapshots to nearest game event → ticks        |
| `quality.py`    | Aggregate issues + alignment → report + verdict            |
| `bundle.py`     | Build / save / load bundles; convert to engine models      |
| `loaders.py`    | High-level load+normalize helpers                          |
| `exporters.py`  | JSON / JSONL file IO (deterministic, sorted keys)          |
| `cli.py`        | `validate` / `build-bundle` / `inspect-bundle`             |
| `adapters/`     | Format readers + generic sports/market adapters            |

## CLI

```bash
python -m src.data.cli validate \
    --game data/examples/raw_game_sample.csv \
    --market data/examples/raw_market_sample.csv

python -m src.data.cli build-bundle \
    --game data/examples/raw_game_sample.csv \
    --market data/examples/raw_market_sample.csv \
    --out data/examples/replay_bundle.json

python -m src.data.cli inspect-bundle --bundle data/examples/replay_bundle.json
```

`validate` exits non-zero when the verdict is `FAIL`, so it can gate a
pipeline. `build-bundle` still writes the bundle on `FAIL` but warns and
exits non-zero.

## Design principle

This phase is not about finding alpha. It is about making bad data
**obvious** so it cannot silently create fake edge. Validation and the
quality report matter as much as the replay itself: missing/negative/
out-of-range prices, crossed books, backwards clocks, orphaned market
snapshots, suspicious gaps, and stale data are all surfaced as structured
issues with severities.
