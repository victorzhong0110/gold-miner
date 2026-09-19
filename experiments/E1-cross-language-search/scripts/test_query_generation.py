"""Offline tests for B/C/M query generation."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

E1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(E1 / "scripts"))
import query_generation as qg  # noqa: E402


class FakeClient:
    def generate_variants(self, task, arm, prompt):
        assert "用户原话" in prompt or "改写" in prompt
        return [
            {
                "variant_query": "injected clipboard manager",
                "variant_lang": "en",
                "api_query": "injected clipboard manager",
            }
        ]


class TestQueryGeneration(unittest.TestCase):
    def test_prompts_exist(self):
        for arm, path in qg.PROMPTS.items():
            self.assertTrue(path.is_file(), arm)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("TODO", text)

    def test_fixture_b_for_dev01(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "B", "fixture")
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["mode"], "fixture")
        self.assertGreaterEqual(len(row["variants"]), 1)
        self.assertTrue(row["prompt_sha256_16"])
        self.assertTrue(row["input_sha256_16"])

    def test_live_without_key_is_blocked(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "C", "live")
        self.assertEqual(row["code"], "owner_blocked")
        self.assertIn("未运行", row["notes"])
        self.assertEqual(row["variants"], [])

    def test_m_fixture_same_language(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "M", "fixture")
        langs = {v["variant_lang"] for v in row["variants"]}
        self.assertEqual(langs, {"zh"})

    def test_cli_fixture(self):
        code = qg.main(
            ["--task-id", "zh2en-dev-01", "--arm", "B", "--mode", "fixture"]
        )
        self.assertEqual(code, 0)

    def test_live_with_injected_client_uses_model(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        row = qg.generate(tasks["zh2en-dev-01"], "C", "live", client=FakeClient())
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["mode"], "live")
        self.assertEqual(row["variants"][0]["variant_query"], "injected clipboard manager")
        self.assertIn("live model client", row["notes"])
        blob = json.dumps(row, ensure_ascii=False)
        self.assertNotIn("sk-", blob)

    def test_live_with_key_still_blocked_without_allow_network(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        env = {
            "OPENAI_API_KEY": "mock-key-not-real",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "OPENAI_MODEL": "mock-model",
        }
        with patch.dict(os.environ, env, clear=False):
            row = qg.generate(tasks["zh2en-dev-01"], "C", "live")
        self.assertEqual(row["code"], "owner_blocked")
        self.assertIn("allow_network", row["notes"])

    def test_allow_network_uses_injected_http_post(self):
        tasks = {t["id"]: t for t in qg.load_queries_yaml(E1 / "queries.yaml")}
        payload_seen = {}

        def fake_post(url, headers, payload, timeout):
            payload_seen["url"] = url
            payload_seen["headers"] = headers
            payload_seen["payload"] = payload
            content = json.dumps(
                {
                    "zh": ["剪贴板 历史"],
                    "en": ["clipboard history"],
                    "notes": "",
                },
                ensure_ascii=False,
            )
            return {
                "status": 200,
                "body": json.dumps({"choices": [{"message": {"content": content}}]}),
            }

        env = {
            "OPENAI_API_KEY": "mock-key-not-real",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "OPENAI_MODEL": "mock-model",
        }
        with patch.dict(os.environ, env, clear=False):
            row = qg.generate(
                tasks["zh2en-dev-01"],
                "C",
                "live",
                allow_network=True,
                http_post=fake_post,
            )
        self.assertEqual(row["code"], "ok")
        self.assertEqual(row["variants"][0]["variant_query"], "剪贴板 历史")
        self.assertIn("example.test", payload_seen["url"])
        self.assertNotIn("mock-key-not-real", json.dumps(row, ensure_ascii=False))

    def test_parse_model_variants_b_c_m(self):
        b = qg.parse_model_variants(
            "B", "zh2en", '{"other_lang":"en","query":"clipboard history tool"}'
        )
        self.assertEqual(b[0]["variant_lang"], "en")
        c = qg.parse_model_variants(
            "C",
            "zh2en",
            '{"zh":["剪贴板"],"en":["clipboard"],"notes":""}',
        )
        self.assertEqual({v["variant_lang"] for v in c}, {"zh", "en"})
        m = qg.parse_model_variants(
            "M",
            "zh2en",
            '{"same_lang":"zh","queries":["剪贴板 历史"],"notes":""}',
        )
        self.assertEqual(m[0]["variant_lang"], "zh")


if __name__ == "__main__":
    unittest.main()
