#!/usr/bin/env bash
# Run the replay simulator from repo root on Linux/macOS
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.replay.simulator "$@"
