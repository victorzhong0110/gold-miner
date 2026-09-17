"""Unit tests for e1_minimal_runner.py. No real network: all HTTP is faked."""

import json
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
        self.assertEqual(out["attempted_requests"], 1)
        self.assertEqual(out["successful_requests"], 1)
        self.assertEqual(out["failed_requests"], 0)
        self.assertEqual(out["cancelled_variants"], 0)
        self.assertEqual(out["requested_budget"], 1)
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(len(out["merged_candidates"]), 1)
        self.assertEqual(len(out["per_query_records"]), 1)

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
        self.assertEqual(out["attempted_requests"], 2)
        self.assertEqual(out["successful_requests"], 2)
        self.assertEqual(out["failed_requests"], 0)
        self.assertEqual(out["cancelled_variants"], 0)
        repos = [c["repo"] for c in out["candidates"]]
        self.assertEqual(repos, ["Owner/Repo", "other/one", "other/two"])
        # per_query_records keeps every hit (2+2 including cross-variant dup).
        self.assertEqual(len(out["per_query_records"]), 4)
        self.assertEqual(len(out["merged_candidates"]), 3)
        # merged retains ALL source associations, not first-seen only.
        first = out["merged_candidates"][0]
        self.assertIn("sources", first)
        self.assertEqual(len(first["sources"]), 2)
        self.assertEqual(
            [s["variant_query"] for s in first["sources"]], ["q1", "q2"]
        )
        self.assertEqual(
            [s["api_query"] for s in first["sources"]], ["q1", "q2"]
        )
        for s in first["sources"]:
            for k in ("variant_query", "api_query", "variant_lang", "rank", "page"):
                self.assertIn(k, s)

    def test_runs_all_variants_even_when_first_fills_merge(self):
        calls = {"n": 0}

        def make_many(prefix, n):
            return make_items(*[f"{prefix}/{i}" for i in range(n)])

        def fake_get(url, headers):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_many("fill", runner.MERGED_TOP_N)
            return make_items("late/only")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="B",
            variants=[
                {"variant_query": "q1", "variant_lang": "zh", "api_query": "q1"},
                {"variant_query": "q2", "variant_lang": "en", "api_query": "q2"},
            ],
            http_get=fake_get,
            sleep_func=noop,
            sleep_seconds=0,
        )
        # Never break outer loop early when one query fills merge.
        self.assertEqual(calls["n"], 2)
        self.assertEqual(out["attempted_requests"], 2)
        self.assertEqual(out["successful_requests"], 2)
        self.assertEqual(len(out["per_query_records"]), runner.MERGED_TOP_N + 1)
        self.assertEqual(len(out["merged_candidates"]), runner.MERGED_TOP_N)
        self.assertEqual(len(out["candidates"]), runner.MERGED_TOP_N)

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
        # Failed attempts count toward cost; success count alone is not cost.
        self.assertEqual(out["attempted_requests"], 2)
        self.assertEqual(out["successful_requests"], 1)
        self.assertEqual(out["failed_requests"], 1)
        self.assertEqual(out["cancelled_variants"], 0)
        self.assertEqual(len(out["errors"]), 1)
        self.assertIn("TimeoutError", out["errors"][0]["error"])
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(len(out["per_query_records"]), 1)
        self.assertEqual(len(out["merged_candidates"]), 1)

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
        self.assertEqual(out["attempted_requests"], 1)
        self.assertEqual(out["successful_requests"], 1)
        self.assertEqual(out["failed_requests"], 0)
        self.assertEqual(out["cancelled_variants"], 1)
        self.assertEqual(out["errors"][-1]["error"], "cancelled")
        self.assertEqual(len(out["per_query_records"]), 1)

    def test_cancel_records_each_remaining_variant(self):
        def fake_get(url, headers):
            raise AssertionError("cancelled before any request, must not call HTTP")

        out = runner.run_method(
            run_id="r1",
            task_id="t1",
            direction="zh2en",
            arm="C",
            variants=[
                {"variant_query": "a", "variant_lang": "zh", "api_query": "a"},
                {"variant_query": "b", "variant_lang": "en", "api_query": "b"},
                {"variant_query": "c", "variant_lang": "zh", "api_query": "c"},
            ],
            http_get=fake_get,
            should_cancel=lambda: True,
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(out["actual_requests"], 0)
        self.assertEqual(out["attempted_requests"], 0)
        self.assertEqual(out["successful_requests"], 0)
        self.assertEqual(out["failed_requests"], 0)
        self.assertEqual(out["cancelled_variants"], 3)
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["merged_candidates"], [])
        self.assertEqual(out["per_query_records"], [])
        self.assertEqual(len(out["errors"]), 3)
        self.assertEqual(
            [e["variant_index"] for e in out["errors"]], [0, 1, 2]
        )
        self.assertTrue(all(e["error"] == "cancelled" for e in out["errors"]))

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

    def test_runner_arms_conform_to_candidates_schema(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "schemas"
            / "candidates.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_arms = set(schema["properties"]["arm"]["enum"])
        # Runner produces GitHub rows for A/B/C/M; D is a tool control and
        # must not be silently recorded as a GitHub run. Schema must allow
        # M and retain A/B/C/D for other record paths.
        self.assertEqual(set(runner.ALLOWED_ARMS), {"A", "B", "C", "M"})
        self.assertEqual(schema_arms, {"A", "B", "C", "D", "M"})
        self.assertTrue(
            set(runner.ALLOWED_ARMS) <= schema_arms,
            f"runner arms {sorted(runner.ALLOWED_ARMS)} not subset of "
            f"schema arms {sorted(schema_arms)}",
        )
        required = schema["required"]
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
            http_get=lambda u, h: make_items("a/one"),
            sleep_func=noop,
            sleep_seconds=0,
        )
        self.assertEqual(len(out["candidates"]), 1)
        for field in required:
            self.assertIn(field, out["candidates"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
