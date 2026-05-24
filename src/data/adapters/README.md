# Data adapters

Adapters turn raw files into normalized canonical models. They are
deliberately thin and source-agnostic.

| Adapter                      | Role                                                      |
|------------------------------|-----------------------------------------------------------|
| `csv_adapter.read_csv`       | CSV file → list of raw dict rows                          |
| `json_adapter.read_json`     | JSON file → list of raw dict rows (list / object / rows)  |
| `generic_sports_adapter`     | game file (CSV/JSON/JSONL) → `CanonicalGameEvent[]`       |
| `generic_market_adapter`     | market file (CSV/JSON/JSONL) → `CanonicalMarketSnapshot[]`|

## Why "generic"?

The generic adapters do not assume any one data provider's schema. They read
rows and hand them to `src.data.normalizer`, which resolves messy field names
(`homeTeam`, `home_team`, `home`; `yesBid`, `bid_yes`; etc.) via alias tables.

## Adding a provider-specific adapter later

When integrating a real historical source, add a module here that:

1. reads the provider's native format (CSV/JSON/Parquet/...),
2. maps its fields onto the canonical alias names (or directly builds
   canonical models), and
3. returns `CanonicalGameEvent[]` / `CanonicalMarketSnapshot[]`.

Keep all provider quirks isolated in the adapter so the rest of the pipeline
stays source-agnostic. No adapter should embed API keys or hit the network —
this layer is local-files-only by design.
