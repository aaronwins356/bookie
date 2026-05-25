# Tennis Live Data Capture

## Overview

Tennis markets on Kalshi are captured using the same `DATA_CAPTURE_ONLY` pipeline
as other markets (`src/live/`). The tennis layer adds sport-aware filtering so
you can find tennis-specific markets quickly.

## Finding Tennis Markets

```bash
# List all open tennis markets
python -m src.live.cli list-markets --sport tennis --status open

# Search by tournament name
python -m src.live.cli list-markets --query "Wimbledon" --status open

# Combine sport filter with tournament query
python -m src.live.cli list-markets --sport tennis --query "ATP" --status open
```

**How filtering works**:
- `--sport tennis` filters by Kalshi series ticker prefix (`KXATP`, `KXWTA`, `KXTEN`)
  and keyword match against the title (`tennis`, `atp`, `wta`, `wimbledon`, etc.)
- `--query <text>` is a case-insensitive substring match against title, series ticker,
  and event ticker.

**Note**: Kalshi's exact series tickers change when new events are added. If `--sport tennis`
returns nothing, try `--query tennis` or `--query atp` as a fallback.

## Recording Tennis Markets

```bash
# Record a specific market for 5 minutes
python -m src.live.cli record \
    --tickers KXATP-WIM-25-DJOKOVIC \
    --seconds 300 \
    --out data/live

# Record multiple markets at once
python -m src.live.cli record \
    --tickers KXATP-WIM-25-DJOKOVIC KXATP-WIM-25-ALCARAZ \
    --seconds 300 \
    --out data/live
```

Raw capture goes to `data/live/YYYY-MM-DD/<ticker>.jsonl`.

## Building a Replay Bundle

```bash
python -m src.live.cli build-bundle \
    --input data/live/2026-07-05/KXATP-WIM-25-DJOKOVIC.jsonl \
    --out data/replays/djokovic_wimbledon_2026.json \
    --ticker KXATP-WIM-25-DJOKOVIC
```

**What the bundle contains**:
- A sequence of `CanonicalMarketSnapshot` ticks from the JSONL recording.
- A placeholder `CanonicalGameEvent` with `status="LIVE_UNKNOWN"` — because
  the live capture only has market data, not game state.
- Quality report warnings: `MISSING_GAME_STATE`, `LIVE_CAPTURE_MARKET_ONLY`.

## Augmenting With Game State

The live capture produces market-only bundles. To get full tennis game state:

1. Use a sports data provider (Sportradar, Genius Sports, OpenLigaDB) to obtain
   point-by-point data aligned to the same timestamps.
2. Construct `TennisState` objects from that data.
3. Pass them to `TennisFeatureExtractor.extract(state, market)` alongside
   the market snapshots from the bundle.

Until full game-state integration is built, the research warnings on all
live-capture bundles remain active:
- `LIVE_CAPTURE_MARKET_ONLY` — market data only, no game state
- `LIVE_CAPTURE_GAME_STATE_ABSENT` — strategies that require game state cannot fire
- `LIVE_CAPTURE_NOT_PROOF` — signals from live capture are not proof of edge

## Training from Captured Data

```bash
python -m src.live.cli train-from-capture \
    --input data/live/2026-07-05/KXATP-WIM-25-DJOKOVIC.jsonl \
    --out data/results/ \
    --ticker KXATP-WIM-25-DJOKOVIC
```

Runs the backtest pipeline on the bundle. All research warnings are propagated
to the `BatchBacktestResult` quality report.

## Kalshi Tennis Market Naming Conventions

| Series Prefix | Tour | Example |
|---------------|------|---------|
| `KXATP` | ATP men's | `KXATP-WIM-25-MATCH001` |
| `KXWTA` | WTA women's | `KXWTA-USO-25-MATCH001` |
| `KXTEN` | Generic tennis | varies |

Grand slam slugs: `AO` (Australian Open), `RG` (Roland Garros), `WIM` (Wimbledon),
`USO` (US Open).

**Disclaimer**: Kalshi naming is not stable across events. Always verify with
`list-markets --sport tennis` before recording.
