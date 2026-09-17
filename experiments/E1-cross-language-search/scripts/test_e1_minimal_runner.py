"""Unit tests for e1_minimal_runner.py. No real network: all HTTP is faked."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_minimal_runner as runner


def noop(_seconds: float) -> None:
    return None


def make_items(*names):
    items = []
    for i, name in enumerate(names, start=1):
        items.append(
            {
                "full_name": name,
                "stargazers_count": i * 10,
                "description": "d",
                "topics": [],
                "text_matches": [{"property": "name"}],
            }
        )
    return {"items": items}


class TestBudgets(unittest.TestCase):
    def test_a_allows_one_variant(self):
        def fake_get(url, headers):
            return make_items("a/one")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="A",
            variants=[
                {
                    "variant_query": "剪贴板历史",
                    "variant_lang": "zh",
                    "api_query": "剪贴板历史",
                }
            ],
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["actual_requests"], 1)
        self.assertEqual(out["requested_budget"], 1)
        self.assertEqual(len(out["candidates"]), 1)

    def test_a_rejects_two_variants(self):
        with self.assertRaises(ValueError):
            runner.run_method(
                run_id="r1",
                task_id="t1",
                direction="zh2en",
                arm="A",
                variants=[
                    {
                        "variant_query": "a",
                        "variant_lang": "zh",
                        "api_query": "a",
                    },
                    {
                        "variant_query": "b",
                        "variant_lang": "zh",
                        "api_query": "b",
                    },
                ],
                http_get=lambda u, h: {"items": []},
                sleep_func=noop,
                sleep_seconds=0,
            )

    def test_d_is_not_a_github_run(self):
        with self.assertRaises(ValueError):
            runner.run_method(
                run_id="r1",
                task_id="t1",
                direction="zh2en",
                arm="D",
                variants=[
                    {"variant_query": "a", "variant_lang": "zh", "api_query": "a"}
                ],
                http_get=lambda u, h: {"items": []},
                sleep_func=noop,
                sleep_seconds=0,
            )

    def test_default_no_network(self):
        with self.assertRaises(RuntimeError):
            runner.run_method(
                run_id="r1",
                task_id="t1",
                direction="zh2en",
                arm="A",
                variants=[
                    {"variant_query": "a", "variant_lang": "zh", "api_query": "a"}
                ],
                sleep_func=noop,
                sleep_seconds=0,
            )


class TestMergeDedup(unittest.TestCase):
    def test_dedup_across_variants_keeps_first(self):
        calls = {"n": 0}

        def fake_get(url, headers):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_items("Owner/Repo", "other/one")
            return make_items("owner/repo", "other/two")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="en2zh",
            arm="C",
            variants=[
                {"variant_query": "q1", "variant_lang": "zh", "api_query": "q1"},
                {"variant_query": "q2", "variant_lang": "en", "api_query": "q2"},
            ],
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["actual_requests"], 2)
        repos = [c["repo"] for c in out["candidates"]]
        self.assertEqual(repos, ["Owner/Repo", "other/one", "other/two"])

    def test_seed_flagging_case_insensitive(self):
        def fake_get(url, headers):
            return make_items("Owner/Seed")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="B",
            variants=[
                {"variant_query": "a", "variant_lang": "zh", "api_query": "a"},
            ],
            seed_repos={"owner/seed"},
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertTrue(out["candidates"][0]["is_seed_target"])

    def test_unknown_fields_preserved(self):
        def fake_get(url, headers):
            return {
                "items": [
                    {
                        "full_name": "x/y",
                        "stargazers_count": 1,
                        "description": None,
                        "topics": [],
                    }
                ]
            }

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="A",
            variants=[
                {"variant_query": "a", "variant_lang": "zh", "api_query": "a"}
            ],
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["candidates"][0]["matched_fields"], ["unknown"])


class TestErrorsCancel(unittest.TestCase):
    def test_variant_error_recorded_not_fabricated(self):
        def fake_get(url, headers):
            if "bad" in url:
                raise TimeoutError("timed out")
            return make_items("good/repo")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="B",
            variants=[
                {"variant_query": "bad", "variant_lang": "zh", "api_query": "bad"},
                {"variant_query": "good", "variant_lang": "en", "api_query": "good"},
            ],
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["actual_requests"], 1)
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("TimeoutError", out["errors"][0]["error"])
        self.assertEqual(len(out["candidates"]), 1)

    def test_cancel_stops_new_requests(self):
        calls = {"n": 0}

        def fake_get(url, headers):
            calls["n"] += 1
            return make_items("a/b")

        state = {"cancel": False}

        def should_cancel():
            return state["cancel"]

        def counting_get(url, headers):
            out = fake_get(url, headers)
            state["cancel"] = True
            return out

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="B",
            variants=[
                {"variant_query": "a", "variant_lang": "zh", "api_query": "a"},
                {"variant_query": "b", "variant_lang": "en", "api_query": "b"},
            ],
            http_get=counting_get,
            should_cancel=should_cancel,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(calls["n"], 1)
        self.assertEqual(out["actual_requests"], 1)
        self.assertEqual(out["errors"][-1]["error"], "cancelled")

    def test_candidate_row_validation(self):
        base = dict(
            run_id="r",
            task_id="t",
            direction="zh2en",
            arm="A",
            variant_query="q",
            variant_lang="zh",
            api_query="q",
            page=1,
            rank=1,
            repo="o/r",
            stars=0,
            matched_fields=["unknown"],
            is_seed_target=False,
            fetched_at="2026-09-17T00:00:00Z",
        )
        runner.build_candidate_row(**base)
        bad = dict(base, arm="D")
        with self.assertRaises(ValueError):
            runner.build_candidate_row(**bad)
        bad2 = dict(base, matched_fields=["title-guess"])
        with self.assertRaises(ValueError):
            runner.build_candidate_row(**bad2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
