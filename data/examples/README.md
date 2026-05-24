# Example raw data

Small synthetic samples used to exercise the Phase 3 data pipeline. They are
**not** real market data and prove no edge — they exist to demonstrate
ingestion, normalization, validation, alignment, and replay.

## Files

| File                     | Purpose                                              |
|--------------------------|------------------------------------------------------|
| `raw_game_sample.csv`    | Game events, CSV, messy headers (`homeTeam`, `clock`)|
| `raw_market_sample.csv`  | Market snapshots, CSV (`yesBid`, `vol`, `oi`)        |
| `raw_game_sample.json`   | Same game data, JSON list, different aliases (`home`)|
| `raw_market_sample.json` | Same market data, JSON `{"rows": [...]}` (`bid_yes`) |

Both formats normalize to the **same** canonical models — that is the point
of the normalizer's field-alias resolution.

## Try it

```bash
python -m src.data.cli validate     --game data/examples/raw_game_sample.csv  --market data/examples/raw_market_sample.csv
python -m src.data.cli build-bundle  --game data/examples/raw_game_sample.csv  --market data/examples/raw_market_sample.csv  --out data/examples/replay_bundle.json
python -m src.data.cli inspect-bundle --bundle data/examples/replay_bundle.json
python -m src.replay.simulator --bundle data/examples/replay_bundle.json
```

The CSV and JSON variants are interchangeable — swap `.csv` for `.json`.
