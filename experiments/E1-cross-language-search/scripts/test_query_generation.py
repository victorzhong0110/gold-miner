"""Offline tests for B/C/M query generation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

E1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(E1 / "scripts"))
import query_generation as qg  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
