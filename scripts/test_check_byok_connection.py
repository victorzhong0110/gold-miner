"""Offline tests for BYOK probe. No network."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import check_byok_connection as byok  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_missing_key(self):
        self.assertEqual(
            byok.classify_config("https://example.com/v1", "m", ""),
            "missing_credentials",
        )

    def test_bad_url(self):
        self.assertEqual(
            byok.classify_config("ftp://x", "m", "k"), "invalid_endpoint"
        )

    def test_http_codes(self):
        self.assertEqual(byok.classify_http(401, "{}"), "auth_rejected")
        self.assertEqual(byok.classify_http(429, "{}"), "rate_limited")
        self.assertEqual(
            byok.classify_http(200, '{"choices":[{"message":{"content":"pong"}}]}'),
            "ok",
        )
        self.assertEqual(byok.classify_http(200, "not-json"), "bad_response")

    def test_redact_key(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-abcdefghijk"}):
            self.assertNotIn("sk-abcdefghijk", byok.redact("token=sk-abcdefghijk"))

    def test_cli_without_key(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            code = byok.main([])
        self.assertEqual(code, 2)


class TestExampleEnv(unittest.TestCase):
    def test_example_has_no_secret_values(self):
        text = (ROOT / "config" / "byok.example.env").read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9]{8,}")
        self.assertNotRegex(text, r"ghp_[A-Za-z0-9]+")


if __name__ == "__main__":
    unittest.main()
