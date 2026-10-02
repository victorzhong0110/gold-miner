"""Offline checks for glossary variants and the frozen variant document."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_glossary_variants as gloss

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
TERMS = ROOT / "experiments" / "E9-glossary" / "terms.yaml"
QUERIES = E1 / "queries.yaml"
FROZEN = E1 / "variants" / "eval-batch-1-glossary.json"

MINI_TERMS = [
    {
        "id": "static-site-generator",
        "zh": ["静态站点生成器", "静态网站生成器", "SSG"],
        "en": ["static site generator", "SSG", "static generator"],
        "notes": "",
    },
    {
        "id": "pomodoro",
        "zh": ["番茄钟", "番茄工作法"],
        "en": ["pomodoro", "pomodoro timer"],
        "notes": "",
    },
]


class TestGlossaryRules(unittest.TestCase):
    def test_exact_zh_phrase_emits_without_padding(self):
        task = {
            "id": "t",
            "direction": "zh2en",
            "query": "静态站点生成器",
        }
        row = gloss.classify_task(task, MINI_TERMS)
        self.assertEqual(row["status"], "covered")
        self.assertEqual(row["matched_term_id"], "static-site-generator")
        self.assertEqual(row["model_requests"], 0)
        self.assertEqual(len(row["arms"]["B"]), 2)
        self.assertEqual(row["arms"]["B"][1]["variant_query"], "static site generator")
        self.assertEqual(row["arms"]["B"][1]["variant_lang"], "en")
        self.assertLessEqual(len(row["arms"]["C"]), 4)
        self.assertEqual(len(row["arms"]["C"]), 3)
        self.assertLessEqual(len(row["arms"]["M"]), 4)
        phrases = {v["variant_query"] for v in row["arms"]["B"] + row["arms"]["C"] + row["arms"]["M"]}
        allowed = {
            "静态站点生成器",
            "静态网站生成器",
            "SSG",
            "static site generator",
            "static generator",
        }
        self.assertTrue(phrases <= allowed)

    def test_remainder_blocks_instead_of_dropping_negation(self):
        task = {
            "id": "zh2en-eval-08",
            "direction": "zh2en",
            "query": "静态站点生成器 不要 node",
        }
        row = gloss.classify_task(task, MINI_TERMS)
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["reason"], "glossary_remainder")
        self.assertEqual(row["arms"]["B"], [])
        self.assertEqual(row["arms"]["C"], [])
        self.assertEqual(row["arms"]["M"], [])
        self.assertIn("node", row["remainder"].lower())

    def test_uncovered_and_ambiguous(self):
        uncovered = gloss.classify_task(
            {"id": "u", "direction": "zh2en", "query": "局域网文件互传 工具"},
            MINI_TERMS,
        )
        self.assertEqual(uncovered["reason"], "glossary_uncovered")
        ambiguous = gloss.classify_task(
            {"id": "a", "direction": "zh2en", "query": "番茄钟 SSG"},
            MINI_TERMS,
        )
        self.assertEqual(ambiguous["reason"], "glossary_ambiguous")
        self.assertEqual(ambiguous["arms"]["B"], [])

    def test_real_eval_batch_has_no_emitted_variants(self):
        from e1_batch import load_queries

        tasks = load_queries(QUERIES)["eval.batch_1"]
        terms = gloss.load_terms(TERMS)
        doc = gloss.build_document(
            tasks, terms, "experiments/E9-glossary/terms.yaml"
        )
        self.assertEqual(doc["model_requests"], 0)
        self.assertFalse(doc["synonym_guarantee"])
        self.assertEqual(len(doc["tasks"]), 20)
        self.assertTrue(all(row["status"] == "blocked" for row in doc["tasks"]))
        self.assertTrue(all(row["arms"]["B"] == [] for row in doc["tasks"]))
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(frozen, doc)

    def test_module_does_not_call_github(self):
        src = Path(gloss.__file__).read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", src)
        self.assertNotIn("urllib", src)
        self.assertNotIn("OPENAI", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
