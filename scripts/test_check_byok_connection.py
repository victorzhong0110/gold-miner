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


class TestReasoningModelOutputs(unittest.TestCase):
    """S6: HTTP 200 used to be reported as success even when nothing usable came back."""

    MAINLAND = "https://api.minimaxi.com/v1"

    def test_truncated_reply_is_not_ok(self):
        body = json.dumps(
            {
                "choices": [
                    {"finish_reason": "length", "message": {"content": "<think>still going</think>"}}
                ]
            }
        )
        self.assertEqual(byok.classify_http(200, body, self.MAINLAND), "output_truncated")

    def test_reasoning_only_reply_is_empty_output(self):
        body = json.dumps(
            {"choices": [{"finish_reason": "stop", "message": {"content": "<think>only thought</think>"}}]}
        )
        self.assertEqual(byok.classify_http(200, body, self.MAINLAND), "empty_output")

    def test_reasoning_plus_answer_is_ok(self):
        body = json.dumps(
            {"choices": [{"finish_reason": "stop", "message": {"content": "<think>plan</think>pong"}}]}
        )
        self.assertEqual(byok.classify_http(200, body, self.MAINLAND), "ok")

    def test_default_budget_matches_extension(self):
        self.assertGreaterEqual(byok.DEFAULT_MAX_TOKENS, 2048)


class TestRegionMismatch(unittest.TestCase):
    """S3: a bare 401 hid the most common cause, a key/host region mismatch."""

    def test_mainland_host_401_is_wrong_region(self):
        body = json.dumps({"error": "unauthorized"})
        self.assertEqual(
            byok.classify_http(401, body, "https://api.minimaxi.com/v1"), "wrong_region"
        )

    def test_international_host_401_is_wrong_region(self):
        body = json.dumps({"error": "unauthorized"})
        self.assertEqual(
            byok.classify_http(401, body, "https://api.minimax.io/v1"), "wrong_region"
        )

    def test_business_code_1004_is_wrong_region(self):
        body = json.dumps({"base_resp": {"status_code": 1004}})
        self.assertEqual(
            byok.classify_http(200, body, "https://api.minimax.io/v1"), "wrong_region"
        )

    def test_unknown_host_401_stays_auth_rejected(self):
        body = json.dumps({"error": "unauthorized"})
        self.assertEqual(
            byok.classify_http(401, body, "https://api.example.com/v1"), "auth_rejected"
        )

    def test_host_region_lookup(self):
        self.assertEqual(byok.host_region("https://api.minimaxi.com/v1"), "mainland")
        self.assertEqual(byok.host_region("https://api.minimax.io/v1"), "international")
        self.assertIsNone(byok.host_region("https://api.example.com/v1"))


class TestExampleEnv(unittest.TestCase):
    def test_example_has_no_secret_values(self):
        text = (ROOT / "config" / "byok.example.env").read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9]{8,}")
        self.assertNotRegex(text, r"ghp_[A-Za-z0-9]+")


if __name__ == "__main__":
    unittest.main()
