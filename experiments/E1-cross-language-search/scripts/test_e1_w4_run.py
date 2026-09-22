"""Offline tests for W4 orchestration. No network."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_glossary_variants as gloss
import e1_w4_run as w4
from e1_batch import load_queries
from test_e1_minimal_runner import make_items

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"


def frozen_settings() -> dict:
    return {
        "freeze": {
            "eval_frozen_commit": "a" * 40,
            "prompts_frozen_commit": "b" * 40,
            "seed_set_frozen_commit": "c" * 40,
            "run_settings_commit": "d" * 40,
        },
        "candidate_merge": {"per_query_top_n": 30},
    }


class TestW4Run(unittest.TestCase):
    def test_refuses_unfrozen_settings(self):
        tasks = load_queries(E1 / "queries.yaml")["eval.batch_1"][:1]
        doc = {"tasks": []}
        with self.assertRaises(RuntimeError):
            w4.run_eval_arms(
                tasks=tasks,
                glossary_doc=doc,
                run_id="t",
                http_get=lambda url, headers: {},
                settings={"freeze": {}},
            )

    def test_blocked_glossary_arms_do_not_call_http(self):
        tasks = load_queries(E1 / "queries.yaml")["eval.batch_1"]
        terms = gloss.load_terms(ROOT / "experiments" / "E9-glossary" / "terms.yaml")
        doc = gloss.build_document(tasks, terms, "terms.yaml")
        calls = {"n": 0}

        def http_get(url, headers):
            calls["n"] += 1
            if calls["n"] > 20:
                raise AssertionError("more than one request per open task")
            return make_items("Owner/Repo", "other/two")

        out = w4.run_eval_arms(
            tasks=tasks,
            glossary_doc=doc,
            run_id="w4-test",
            http_get=http_get,
            settings=frozen_settings(),
            sleep_func=lambda _s: None,
            sleep_seconds=0,
        )
        self.assertEqual(calls["n"], 20)
        self.assertEqual(out["model_requests"], 0)
        self.assertEqual(out["d_status"], "未运行")
        for arm in ("B", "C", "M"):
            self.assertEqual(out["arms"][arm]["totals"]["tasks_blocked"], 20)
            self.assertEqual(out["arms"][arm]["totals"]["attempted_requests"], 0)
        self.assertEqual(out["arms"]["A"]["totals"]["successful_requests"], 20)

    def test_seed_hit_uses_only_returned_rows(self):
        rows = w4.load_seed_rows(E1 / "seed-set.jsonl")
        calls = []

        def http_get(url, headers):
            calls.append(url)
            target = rows[len(calls) - 1]["repo"]
            if len(calls) == 1:
                return make_items("other/miss", target)
            return make_items("other/miss", "other/also")

        out = w4.run_seed_arm_a(
            rows=rows,
            run_id="seed-test",
            http_get=http_get,
            sleep_func=lambda _s: None,
            sleep_seconds=0,
        )
        self.assertEqual(len(calls), 8)
        self.assertEqual(out["totals"]["attempted_requests"], 8)
        first = out["hits"][0]
        self.assertTrue(first["hit_at_30"])
        self.assertEqual(first["rank_in_merged_top_30"], 2)
        self.assertFalse(out["hits"][1]["hit_at_30"])
        flagged = out["task_results"][0]["merged_candidates"]
        self.assertTrue(any(row["is_seed_target"] for row in flagged))


if __name__ == "__main__":
    unittest.main(verbosity=2)
