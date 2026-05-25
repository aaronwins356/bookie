# Kalshi Live Data Capture

**Mode: DATA_CAPTURE_ONLY — no orders are placed.**

This system connects to the Kalshi API to record live orderbook and market data
for research and backtesting. It does not place trades.

---

## 1. Create an API Key

1. Log in to [kalshi.com](https://kalshi.com)
2. Go to **Account → API** (or Settings → API Keys)
3. Create a new API key — select **read-only** access if available
4. Download your RSA private key as a `.pem` file
5. Store the `.pem` file somewhere safe (e.g., `~/.kalshi/key.pem`)

**Never commit your `.pem` file to git.** It is git-ignored by this repo.

---

## 2. Set Environment Variables

```bash
export KALSHI_KEY_ID="your-key-id-from-dashboard"
export KALSHI_PRIVATE_KEY_PATH="$HOME/.kalshi/key.pem"

# Optional overrides (defaults shown):
# export KALSHI_API_BASE_URL="https://external-api.kalshi.com/trade-api/v2"
# export KALSHI_WS_URL="wss://external-api-ws.kalshi.com/trade-api/ws/v2"
```

Add these to your `~/.bashrc` or `~/.zshrc` for persistence.

---

## 3. Install Live Dependencies

```bash
cd ~/projects/bookie
.venv/bin/pip install -e ".[dev,live]"
```

---

## 4. Run Doctor

Check that your environment is correctly configured:

```bash
python -m src.live.cli doctor
```

Expected output when configured:
```
  DIAGNOSIS
  OK — environment is configured for live data capture.
  IMPORTANT: This system is DATA_CAPTURE_ONLY. No orders will be placed.
```

---

## 5. List Markets

Search for available markets by series, event, or status:

```bash
# List all open KXBTC15M markets
python -m src.live.cli list-markets --series KXBTC15M --status open

# List by specific event
python -m src.live.cli list-markets --event KXBTC15M-25MAY

# Get a specific ticker
python -m src.live.cli list-markets --ticker KXBTC15M-25MAY-BTC15T32000
```

---

## 6. Record Live Data

Stream live WS messages and write them to JSONL:

```bash
python -m src.live.cli record \
  --tickers KXBTC15M-25MAY-BTC15T32000 \
  --seconds 300 \
  --out data/live
```

Output files are written to `data/live/YYYY-MM-DD/<ticker>.jsonl`.
Multiple tickers can be recorded simultaneously:

```bash
python -m src.live.cli record \
  --tickers TICKER1 TICKER2 TICKER3 \
  --seconds 3600 \
  --out data/live
```

---

## 7. Convert Capture to Bundle

```bash
python -m src.live.cli build-bundle \
  --input data/live/2025-05-25/KXBTC15M-25MAY-BTC15T32000.jsonl \
  --out data/live/KXBTC15M-25MAY-BTC15T32000_bundle.json
```

---

## Safety Notes

- **No orders are placed.** The `record` command only subscribes to market data.
- The WS client only sends `subscribe` commands, never `order` commands.
- All secrets come from environment variables — never from the codebase.
- `.pem` files and `.jsonl` capture files are git-ignored.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `KALSHI_KEY_ID is not set` | Run `export KALSHI_KEY_ID="..."` |
| `FILE NOT FOUND` for key path | Check `KALSHI_PRIVATE_KEY_PATH` points to real `.pem` |
| `missing dependency: cryptography` | Run `pip install -e ".[live]"` |
| WS connection refused | Check network; Kalshi may require VPN-free connection |
| Empty orderbook | Market may be closed or low-liquidity |
