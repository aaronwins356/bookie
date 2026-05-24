# Linux Plug-and-Play Guide

## Requirements

- Python 3.11+
- pip or uv
- No system packages needed (pure Python)

## Setup

```bash
git clone https://github.com/aaronwins356/bookie.git
cd bookie

# Option A — pip
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Option B — uv (faster)
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Run replay

```bash
python -m src.replay.simulator
python -m src.replay.simulator --scenario blowout
```

## Run tests

```bash
pytest tests/ -v
```

## Future: Ollama integration

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3

# Set env var (future)
# export BOOKIE_BRAIN=ollama
# export OLLAMA_MODEL=llama3
python -m src.replay.simulator
```

## Future: MCP server

When MCP support is added, run the bookie MCP server with:

```bash
# (not yet implemented)
python -m src.mcp.server
```

## Systemd service (future live trading)

```ini
[Unit]
Description=Bookie trading engine
After=network.target

[Service]
Type=simple
User=bookie
WorkingDirectory=/opt/bookie
ExecStart=/opt/bookie/.venv/bin/python -m src.engine.main
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## What still needs Linux integration

1. **Live exchange adapter** — replace `MockExecutionAdapter` with `KalshiAdapterStub` implementation
2. **WebSocket feed** — replace `MockMarketAdapter` with real-time price feed
3. **Persistent audit log** — write `AuditLog` entries to a file or database
4. **Scheduler** — cron or systemd timer for periodic tick execution
5. **Dashboard / TUI** — wire `DecisionLoop` output to Textual or Rich live display
6. **Ollama brain** — replace `LocalBrain.classify_regime()` with Ollama API call
