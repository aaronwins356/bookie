from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.live.env import (
    DEFAULT_REST_BASE,
    DEFAULT_WS_URL,
    LiveEnv,
    check_live_deps,
    load_env,
    validate_env,
)


class TestLoadEnv:
    def test_defaults_when_no_env(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY_PATH", "KALSHI_API_BASE_URL", "KALSHI_WS_URL"):
                os.environ.pop(key, None)
            env = load_env()
        assert env.key_id == ""
        assert env.private_key_path is None
        assert env.api_base_url == DEFAULT_REST_BASE
        assert env.ws_url == DEFAULT_WS_URL

    def test_reads_key_id(self):
        with patch.dict(os.environ, {"KALSHI_KEY_ID": "test-key-123"}):
            env = load_env()
        assert env.key_id == "test-key-123"

    def test_reads_key_path(self, tmp_path):
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        with patch.dict(os.environ, {"KALSHI_PRIVATE_KEY_PATH": str(pem)}):
            env = load_env()
        assert env.private_key_path == pem

    def test_reads_url_overrides(self):
        with patch.dict(os.environ, {
            "KALSHI_API_BASE_URL": "https://custom.api/v2",
            "KALSHI_WS_URL": "wss://custom.ws/v2",
        }):
            env = load_env()
        assert env.api_base_url == "https://custom.api/v2"
        assert env.ws_url == "wss://custom.ws/v2"


class TestLiveEnv:
    def test_is_configured_true(self, tmp_path):
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        env = LiveEnv(
            key_id="abc123",
            private_key_path=pem,
            api_base_url=DEFAULT_REST_BASE,
            ws_url=DEFAULT_WS_URL,
        )
        assert env.is_configured is True

    def test_is_configured_false_no_key_id(self, tmp_path):
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        env = LiveEnv(
            key_id="",
            private_key_path=pem,
            api_base_url=DEFAULT_REST_BASE,
            ws_url=DEFAULT_WS_URL,
        )
        assert env.is_configured is False

    def test_key_id_display_redacts(self):
        env = LiveEnv("abcdefghij", None, DEFAULT_REST_BASE, DEFAULT_WS_URL)
        display = env.key_id_display
        assert "abcdef" in display
        assert "ghij" not in display

    def test_key_id_display_not_set(self):
        env = LiveEnv("", None, DEFAULT_REST_BASE, DEFAULT_WS_URL)
        assert env.key_id_display == "<NOT SET>"


class TestValidateEnv:
    def test_no_key_id_reports_problem(self):
        env = LiveEnv("", Path("/some/key.pem"), DEFAULT_REST_BASE, DEFAULT_WS_URL)
        problems = validate_env(env)
        assert any("KALSHI_KEY_ID" in p for p in problems)

    def test_no_path_reports_problem(self):
        env = LiveEnv("key123", None, DEFAULT_REST_BASE, DEFAULT_WS_URL)
        problems = validate_env(env)
        assert any("KALSHI_PRIVATE_KEY_PATH" in p for p in problems)

    def test_missing_pem_file_reports_problem(self, tmp_path):
        env = LiveEnv("key123", tmp_path / "nonexistent.pem", DEFAULT_REST_BASE, DEFAULT_WS_URL)
        problems = validate_env(env)
        assert any("missing" in p.lower() or "FILE NOT FOUND" in p.upper() or "missing file" in p.lower() for p in problems)

    def test_valid_env_no_problems(self, tmp_path):
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        env = LiveEnv("key123", pem, DEFAULT_REST_BASE, DEFAULT_WS_URL)
        assert validate_env(env) == []


class TestCheckLiveDeps:
    def test_returns_list(self):
        missing = check_live_deps()
        assert isinstance(missing, list)

    def test_missing_dep_detected(self):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "cryptography":
                raise ImportError("mocked missing")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            missing = check_live_deps()
        assert "cryptography" in missing
