from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.live.kalshi_auth import KalshiSigner


class TestKalshiSigner:
    def _make_signer(self, key_id: str = "test-key") -> KalshiSigner:
        return KalshiSigner(key_id=key_id, key_path=Path("/fake/key.pem"))

    def _mock_crypto(self):
        """Return a mock private key and patch cryptography imports."""
        mock_key = MagicMock()
        fake_signature = b"\x01\x02\x03\x04" * 64  # 256 bytes
        mock_key.sign.return_value = fake_signature
        return mock_key, fake_signature

    def test_make_headers_returns_required_keys(self):
        signer = self._make_signer()
        mock_key, fake_sig = self._mock_crypto()
        signer._private_key = mock_key

        mock_hashes = MagicMock()
        mock_padding = MagicMock()
        mock_padding.PSS = MagicMock(return_value=MagicMock())
        mock_padding.MGF1 = MagicMock(return_value=MagicMock())
        mock_hashes.SHA256 = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "cryptography.hazmat.primitives.hashes": mock_hashes,
            "cryptography.hazmat.primitives.asymmetric.padding": mock_padding,
            "cryptography": MagicMock(),
            "cryptography.hazmat": MagicMock(),
            "cryptography.hazmat.primitives": MagicMock(),
            "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        }):
            headers = signer.make_headers("GET", "/markets")

        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "Content-Type" in headers

    def test_key_id_in_header(self):
        signer = self._make_signer("my-key-id-abc")
        mock_key, _ = self._mock_crypto()
        signer._private_key = mock_key

        mock_hashes = MagicMock()
        mock_padding = MagicMock()
        mock_padding.PSS = MagicMock(return_value=MagicMock())
        mock_padding.MGF1 = MagicMock(return_value=MagicMock())
        mock_hashes.SHA256 = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "cryptography.hazmat.primitives.hashes": mock_hashes,
            "cryptography.hazmat.primitives.asymmetric.padding": mock_padding,
            "cryptography": MagicMock(),
            "cryptography.hazmat": MagicMock(),
            "cryptography.hazmat.primitives": MagicMock(),
            "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        }):
            headers = signer.make_headers("GET", "/markets")

        assert headers["KALSHI-ACCESS-KEY"] == "my-key-id-abc"

    def test_timestamp_is_numeric(self):
        signer = self._make_signer()
        mock_key, _ = self._mock_crypto()
        signer._private_key = mock_key

        mock_hashes = MagicMock()
        mock_padding = MagicMock()
        mock_padding.PSS = MagicMock(return_value=MagicMock())
        mock_padding.MGF1 = MagicMock(return_value=MagicMock())
        mock_hashes.SHA256 = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "cryptography.hazmat.primitives.hashes": mock_hashes,
            "cryptography.hazmat.primitives.asymmetric.padding": mock_padding,
            "cryptography": MagicMock(),
            "cryptography.hazmat": MagicMock(),
            "cryptography.hazmat.primitives": MagicMock(),
            "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        }):
            headers = signer.make_headers("GET", "/markets")

        ts = headers["KALSHI-ACCESS-TIMESTAMP"]
        assert ts.isdigit(), f"Timestamp should be digits, got: {ts}"
        assert int(ts) > 1_700_000_000_000, "Timestamp should be milliseconds since epoch"

    def test_signature_is_base64(self):
        signer = self._make_signer()
        mock_key, fake_sig = self._mock_crypto()
        signer._private_key = mock_key

        mock_hashes = MagicMock()
        mock_padding = MagicMock()
        mock_padding.PSS = MagicMock(return_value=MagicMock())
        mock_padding.MGF1 = MagicMock(return_value=MagicMock())
        mock_hashes.SHA256 = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "cryptography.hazmat.primitives.hashes": mock_hashes,
            "cryptography.hazmat.primitives.asymmetric.padding": mock_padding,
            "cryptography": MagicMock(),
            "cryptography.hazmat": MagicMock(),
            "cryptography.hazmat.primitives": MagicMock(),
            "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        }):
            headers = signer.make_headers("POST", "/some/path")

        sig_b64 = headers["KALSHI-ACCESS-SIGNATURE"]
        # Must be decodable as base64
        decoded = base64.b64decode(sig_b64)
        assert len(decoded) > 0

    def test_missing_cryptography_raises_import_error(self):
        signer = self._make_signer()
        with patch.dict("sys.modules", {"cryptography": None}):
            import importlib
            # The error is raised inside make_headers when importing
            with pytest.raises((ImportError, TypeError)):
                # Force the import to fail by making _get_key raise
                with patch.object(signer, "_get_key", side_effect=ImportError("no cryptography")):
                    signer.make_headers("GET", "/markets")

    def test_method_uppercased_in_message(self):
        """Verify the signer calls sign with method uppercased."""
        signer = self._make_signer()
        mock_key, _ = self._mock_crypto()
        signer._private_key = mock_key
        signed_messages = []

        def capture_sign(message, *args, **kwargs):
            signed_messages.append(message)
            return b"\x00" * 256

        mock_key.sign.side_effect = capture_sign

        mock_hashes = MagicMock()
        mock_padding = MagicMock()
        mock_padding.PSS = MagicMock(return_value=MagicMock())
        mock_padding.MGF1 = MagicMock(return_value=MagicMock())
        mock_hashes.SHA256 = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "cryptography.hazmat.primitives.hashes": mock_hashes,
            "cryptography.hazmat.primitives.asymmetric.padding": mock_padding,
            "cryptography": MagicMock(),
            "cryptography.hazmat": MagicMock(),
            "cryptography.hazmat.primitives": MagicMock(),
            "cryptography.hazmat.primitives.asymmetric": MagicMock(),
        }):
            signer.make_headers("get", "/markets")

        assert signed_messages, "sign() should have been called"
        msg = signed_messages[0].decode("utf-8")
        assert "GET" in msg, f"Message should contain uppercase GET, got: {msg}"
