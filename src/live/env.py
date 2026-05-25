from __future__ import annotations

"""
Environment variable handling for the live data capture system.

Reads only:
  KALSHI_KEY_ID            — API key identifier
  KALSHI_PRIVATE_KEY_PATH  — path to RSA private key PEM file
  KALSHI_API_BASE_URL      — optional REST base URL override
  KALSHI_WS_URL            — optional WebSocket URL override

Secret values are never logged or printed.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

DEFAULT_REST_BASE = "https://external-api.kalshi.com/trade-api/v2"
DEFAULT_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"


@dataclass
class LiveEnv:
    key_id: str
    private_key_path: Optional[Path]  # None when env var is not set
    api_base_url: str
    ws_url: str

    @property
    def is_configured(self) -> bool:
        return bool(self.key_id and self.private_key_path)

    @property
    def key_id_display(self) -> str:
        """Safe display: shows first 6 chars then redacted."""
        if not self.key_id:
            return "<NOT SET>"
        return self.key_id[:6] + "..." if len(self.key_id) > 6 else "***"


def load_env() -> LiveEnv:
    path_str = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    return LiveEnv(
        key_id=os.environ.get("KALSHI_KEY_ID", ""),
        private_key_path=Path(path_str) if path_str else None,
        api_base_url=os.environ.get("KALSHI_API_BASE_URL", DEFAULT_REST_BASE),
        ws_url=os.environ.get("KALSHI_WS_URL", DEFAULT_WS_URL),
    )


def validate_env(env: LiveEnv) -> List[str]:
    """Return list of problem strings. Empty list = fully configured."""
    problems: List[str] = []
    if not env.key_id:
        problems.append("KALSHI_KEY_ID is not set")
    if not env.private_key_path:
        problems.append("KALSHI_PRIVATE_KEY_PATH is not set")
    elif not env.private_key_path.exists():
        problems.append(
            f"KALSHI_PRIVATE_KEY_PATH points to a missing file: {env.private_key_path}"
        )
    return problems


def check_live_deps() -> List[str]:
    """Return list of missing optional dependency names."""
    missing: List[str] = []
    for pkg, import_name in [
        ("cryptography", "cryptography"),
        ("requests", "requests"),
        ("websockets", "websockets"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    return missing
