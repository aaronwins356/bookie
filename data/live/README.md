# data/live/

Live market capture data — DATA_CAPTURE_ONLY.

## Structure

```
data/live/
└── YYYY-MM-DD/
    └── <ticker>.jsonl    ← one JSONL record per WS message
```

## Notes

- All `.jsonl` files in this directory are git-ignored (real market data is not committed).
- To record: `python -m src.live.cli record --tickers TICKER --seconds 60 --out data/live`
- To convert: `python -m src.live.cli build-bundle --input data/live/YYYY-MM-DD/TICKER.jsonl --out data/live/TICKER_bundle.json`
- No orders are ever placed by the recorder.
