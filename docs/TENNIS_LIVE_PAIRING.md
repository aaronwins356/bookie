# Tennis Live Score Pairing

## Overview

The pairing pipeline connects live tennis score data with Kalshi market snapshots
so that captured data can be replayed with real game context — no LIVE_UNKNOWN
placeholders, real TennisState on every tick.

## Architecture

```
TennisScoreProvider (interface)
    │
    ├── MockProvider (built-in, no external calls)
    └── [future: SportradarProvider, GeniusSportsProvider, ...]
    │
    ▼
TennisLiveFeed          ──polls provider──► (TennisState, timestamp)
    │                                              │
    │                                              ▼
    │                              TennisLiveRecorder
    │                              writes JSONL to:
    │                              data/live/tennis/YYYY-MM-DD/
    │
    │ (separately)
    ▼
MatchPairing            ──fuzzy score──► PairingResult (confidence 0–1)
    │                   player names,
    │                   tournament names,
    │                   tour/series
    ▼
tennis_to_bundle.py     ──convert──► ReplayBundle (sport="tennis", real game events)
    │
    ▼
Existing backtest engine (no changes needed)
```

## CLI Commands

```bash
# List live tennis matches from the score provider
python -m src.sports.tennis.cli list-live

# Find Kalshi markets that match live matches (uses mock markets if no Kalshi auth)
python -m src.sports.tennis.cli pair-markets --status open
python -m src.sports.tennis.cli pair-markets --mock-markets --threshold 0.55

# Record one paired (match + market) for N seconds
python -m src.sports.tennis.cli record-paired \
    --match-id MOCK-001 \
    --ticker KXATP-WIM26-SF001 \
    --seconds 300 \
    --out data/live/tennis

# Convert a paired JSONL capture to a ReplayBundle
python -m src.sports.tennis.cli build-bundle \
    --input data/live/tennis/2026-07-04/MOCK-001__KXATP-WIM26-SF001.jsonl \
    --out data/replays/djokovic_wimbledon.json

# Run backtest on a paired capture
python -m src.sports.tennis.cli backtest-capture \
    --input data/live/tennis/2026-07-04/MOCK-001__KXATP-WIM26-SF001.jsonl \
    --out data/backtests/tennis_capture_check
```

## Score Provider Interface

All providers implement `TennisScoreProvider` (abstract base):

```python
class TennisScoreProvider(ABC):
    def list_live_matches(self) -> List[TennisMatchInfo]: ...
    def get_match_state(self, match_id: str) -> TennisState: ...
    def stream_match_states(self, match_id: str, poll_interval: float) -> Iterator[TennisState]: ...
```

### MockProvider

Built-in, zero-dependency. Returns three pre-canned matches:
- `MOCK-001`: Djokovic vs Alcaraz — Wimbledon, break point (0-40 at 3-3 in set 1)
- `MOCK-002`: Sinner vs Zverev — US Open, post-break momentum
- `MOCK-003`: Swiatek vs Sabalenka — Roland Garros, tiebreak decider

`stream_match_states()` advances the score by one point per tick, giving a realistic
non-static sequence for recorder integration tests.

### Adding a Real Provider

Implement `TennisScoreProvider` and pass it to `TennisLiveFeed`:

```python
class SportradarProvider(TennisScoreProvider):
    def list_live_matches(self) -> List[TennisMatchInfo]:
        ...  # call Sportradar API

from src.sports.tennis.live_feed import TennisLiveFeed
feed = TennisLiveFeed(SportradarProvider(api_key=...))
```

## Match Pairing Algorithm

`match_pairing.score_pair(match, market)` returns a `PairingResult` with `confidence ∈ [0, 1]`:

| Component | Weight | How scored |
|-----------|--------|-----------|
| Player names | 0.50 | SequenceMatcher ratio on name tokens extracted from market title |
| Tournament | 0.30 | Grand slam abbreviation match + fuzzy token match |
| Tour/Series | 0.20 | ATP/WTA keyword in series ticker or title |

Pairs below `threshold` (default **0.55**) are rejected. One market can only be
claimed by one match; the best-scoring unclaimed match wins each market.

### Low-confidence rejection

```python
from src.sports.tennis.match_pairing import pair_matches_to_markets
accepted, rejected = pair_matches_to_markets(matches, markets, threshold=0.55)
for r in rejected:
    print(f"REJECTED: {r.match.display_name} — {r.reason} (best={r.best_confidence:.2f})")
```

## JSONL Record Format

Each JSONL line written by `TennisLiveRecorder`:

```json
{
    "received_at": "2026-07-04T14:08:00.123456+00:00",
    "record_type": "paired",
    "match_id": "MOCK-001",
    "ticker": "KXATP-WIM26-SF001",
    "tennis_state": {
        "match_id": "MOCK-001",
        "player_a": "Djokovic N.",
        "sets_a": 0, "sets_b": 0,
        "games_a": 3, "games_b": 3,
        "points_a": 0, "points_b": 3,
        "server": "A",
        "tiebreak": false,
        ...
    },
    "market_snapshot": {
        "yes_bid": 33.0, "yes_ask": 37.0,
        "volume": 380, ...
    }
}
```

When the tennis feed is unavailable, `record_market_only()` writes `record_type="market_only"` without `tennis_state`. These produce LIVE_UNKNOWN placeholder game events in the bundle and a `PARTIAL_GAME_STATE` quality warning.

## Bundle Output

`tennis_to_bundle.tennis_jsonl_to_bundle()` produces a `ReplayBundle` with:
- `sport = "tennis"`
- `league` = tour value from the first tick with real state (e.g., "ATP")
- `source_metadata["has_tennis_state"] = True` when all ticks have real state
- `source_metadata["capture_mode"] = "TENNIS_PAIRED"`
- No `MISSING_GAME_STATE` quality issue when all ticks have state
- `PARTIAL_GAME_STATE` warning if some ticks are market-only

## Output Directory Layout

```
data/live/tennis/
└── 2026-07-04/
    ├── MOCK-001__KXATP-WIM26-SF001.jsonl   # paired records
    └── market_only__KXATP-WIM26-SF001.jsonl # fallback records
```

## Safety

- No orders are placed anywhere in this module.
- `TennisScoreProvider` and its implementations are **read-only** by interface contract.
- `MockProvider` makes no network calls.
- Kalshi connectivity requires explicit env var setup (`KALSHI_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`).
  The CLI falls back to mock markets if env vars are absent.
