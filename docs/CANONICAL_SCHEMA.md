# Canonical Schema

The canonical models (`src/data/schemas.py`) are the normalized, validated
internal representation that all raw data is converted into. They are
deliberately separate from the engine runtime models (`src.models`):
canonical models carry richer provenance (timestamps, source, league) and
are the on-disk replay-bundle format. Conversion to engine models happens at
replay time via `bundle.to_engine_ticks`.

All models are plain dataclasses with explicit `to_dict` / `from_dict` for
deterministic serialization.

## CanonicalGameEvent

A single observation of a game's state at a point in time.

| Field                     | Type            | Notes                                |
|---------------------------|-----------------|--------------------------------------|
| `event_id`                | str             | stable game/event id                 |
| `sport`                   | str             | e.g. "NFL"                           |
| `league`                  | str             | e.g. "NFL"                           |
| `home_team` / `away_team` | str             |                                      |
| `scheduled_start`         | str? (ISO UTC)  | optional kickoff time                |
| `status`                  | str             | raw status (e.g. "in_progress")      |
| `period`                  | str             | raw period (e.g. "1H", "2H", "OT")   |
| `clock_seconds_remaining` | int             | seconds left in current period       |
| `home_score`/`away_score` | int             |                                      |
| `possession`              | str?            | team in possession                   |
| `timestamp`               | str (ISO UTC)   | observation time                     |

## CanonicalMarketSnapshot

A single observation of a binary market contract.

| Field            | Type           | Notes                                       |
|------------------|----------------|---------------------------------------------|
| `market_id`      | str            |                                             |
| `event_id`       | str            | links to a CanonicalGameEvent               |
| `timestamp`      | str (ISO UTC)  |                                             |
| `yes_bid`/`yes_ask` | float       | cents 0–100                                 |
| `no_bid`/`no_ask`   | float       | derived from YES if absent (100 − yes side) |
| `last_price`     | float?         | last traded price                           |
| `volume`         | int            | contracts traded                            |
| `open_interest`  | int            |                                             |
| `liquidity_score`| float          | derived from volume+OI if absent            |
| `source`         | str            | feed name / provenance                      |

Properties: `mid = (yes_bid + yes_ask)/2`, `spread = yes_ask − yes_bid`.

## CanonicalOrderbookSnapshot

Optional depth snapshot (not required for basic replay).

| Field        | Type                      | Notes                       |
|--------------|---------------------------|-----------------------------|
| `market_id`  | str                       |                             |
| `timestamp`  | str (ISO UTC)             |                             |
| `yes_bids` … | list[(price, size)]       | YES/NO bid & ask ladders    |
| `depth_score`| float                     | aggregate depth metric      |

## CanonicalReplayTick

One aligned moment: a market snapshot + the nearest game event.

| Field                | Type                          | Notes                          |
|----------------------|-------------------------------|--------------------------------|
| `timestamp`          | str (ISO UTC)                 | the snapshot time              |
| `game_event`         | CanonicalGameEvent            |                                |
| `market_snapshot`    | CanonicalMarketSnapshot       |                                |
| `orderbook_snapshot` | CanonicalOrderbookSnapshot?   | optional                       |
| `metadata`           | dict                          | `lag_seconds`, `stale_*` flags |

## DataQualityReport

| Field                       | Meaning                                          |
|-----------------------------|--------------------------------------------------|
| `total_game_rows`           | game events ingested                             |
| `total_market_rows`         | market snapshots ingested                        |
| `total_aligned_ticks`       | ticks produced by the aligner                    |
| `dropped_rows`              | snapshots dropped (no event within max lag)      |
| `info/warning/error/fatal_count` | issue counts by severity                    |
| `time_range_start/end`      | overall data time span                           |
| `max_timestamp_gap_seconds` | largest gap across the merged stream             |
| `stale_market_count`        | ticks following a market-feed gap                |
| `stale_game_count`          | ticks whose attached game event is far in time   |
| `price_issue_count`         | price/cross/consistency issues                   |
| `liquidity_issue_count`     | zero/negative liquidity issues                   |
| `verdict`                   | PASS / PASS_WITH_WARNINGS / FAIL                 |
| `issues`                    | the full `ValidationIssue` list                  |

**Verdict rule:** any ERROR/FATAL → FAIL; else any WARNING → PASS_WITH_WARNINGS;
else PASS.

## ReplayBundle

| Field             | Type                    | Notes                                |
|-------------------|-------------------------|--------------------------------------|
| `bundle_id`       | str                     | content hash (deterministic)         |
| `created_at`      | str (ISO UTC)           | data-derived (latest tick) → stable  |
| `sport`/`league`  | str                     |                                      |
| `event_id`        | str                     |                                      |
| `ticks`           | CanonicalReplayTick[]   | deterministic timestamp order        |
| `quality_report`  | DataQualityReport       |                                      |
| `source_metadata` | dict                    | input file paths, etc.               |

## ValidationIssue

| Field           | Type      | Notes                                  |
|-----------------|-----------|----------------------------------------|
| `severity`      | Severity  | INFO / WARNING / ERROR / FATAL         |
| `code`          | str       | machine-readable (e.g. `MARKET_YES_CROSSED`) |
| `message`       | str       | human-readable detail                  |
| `index`         | int?      | source row index                       |
| `timestamp`     | str?      | relevant timestamp                     |
| `suggested_fix` | str?      | optional remediation hint              |
