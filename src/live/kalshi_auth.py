from __future__ import annotations

"""
Kalshi RSA-PSS request signing.

Signature covers: timestamp_ms + HTTP_METHOD_UPPER + path
Headers produced:
  KALSHI-ACCESS-KEY        — key identifier (not secret)
  KALSHI-ACCESS-TIMESTAMP  — milliseconds since epoch
  KALSHI-ACCESS-SIGNATURE  — base64(RSA-PSS(SHA-256, message))

Private key is loaded lazily and cached. The key bytes are never logged.
"""

import base64
import time
from pathlib import Path
from typing import Dict, Optional


def _load_private_key(key_path: Path):
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise ImportError(
            "Install 'cryptography' to use Kalshi auth: pip install cryptography"
        ) from exc
    with open(key_path, "rb") as fh:
        return serialization.load_pem_private_key(fh.read(), password=None)


class KalshiSigner:
    """Signs Kalshi API requests with RSA-PSS. Thread-safe after first use."""

    def __init__(self, key_id: str, key_path: Path) -> None:
        self._key_id = key_id
        self._key_path = key_path
        self._private_key = None

    def _get_key(self):
        if self._private_key is None:
            self._private_key = _load_private_key(self._key_path)
        return self._private_key

    def make_headers(self, method: str, path: str) -> Dict[str, str]:
        """Return auth headers for a single request. Never logs key material."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError as exc:
            raise ImportError(
                "Install 'cryptography' to use Kalshi auth: pip install cryptography"
            ) from exc

        timestamp_ms = str(int(time.time() * 1000))
        message = (timestamp_ms + method.upper() + path).encode("utf-8")
        key = self._get_key()
        signature = key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
            "Content-Type": "application/json",
        }

    @staticmethod
    def sign_message(private_key, message: bytes) -> str:
        """Low-level helper used in tests. Signs raw bytes, returns base64."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError as exc:
            raise ImportError("Install 'cryptography'") from exc
        sig = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode("ascii")
