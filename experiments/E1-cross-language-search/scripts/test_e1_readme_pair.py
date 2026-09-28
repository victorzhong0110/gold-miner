"""Offline tests for the default vs in:readme pairing. No network."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_readme_pair as pair
from test_e1_minimal_runner import make_items

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
SCRIPT = Path(__file__).resolve().parent / "e1_readme_pair.py"


def task(task_id: str, query: str, direction: str = "zh2en", repo: str | None = None) -> dict:
    row = {
        "id": task_id,
        "direction": direction,
        "type": "open",
        "query": query,
        "need": query,
        "written_at": "2026-09-17",
    }
    if repo:
        row["repo"] = repo
    return row


class TestReadmeQuery(unittest.TestCase):
    def test_appends_qualifier_once(self):
        self.assertEqual(pair.readme_api_query("局域网文件互传 工具"), "局域网文件互传 工具 in:readme")
        self.assertEqual(
            pair.readme_api_query("局域网文件互传 工具 in:readme"),
            "局域网文件互传 工具 in:readme",
        )

    def test_variant_keeps_original_words(self):
        row = pair.build_readme_variants(task("zh2en-eval-01", "局域网文件互传 工具"))[0]
        self.assertEqual(row["variant_query"], "局域网文件互传 工具")
        self.assertEqual(row["api_query"], "局域网文件互传 工具 in:readme")
        self.assertNotIn("in:readme", row["variant_query"])


class TestPairRun(unittest.TestCase):
    def test_stops_after_rate_limit(self):
        calls = {"n": 0}

        def http_get(url, headers):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("HTTP Error 403: rate limit exceeded")
            return make_items("Owner/Repo")

        tasks = [
            task("t1", "alpha tool"),
            task("t2", "beta tool"),
        ]
        out = pair.run_pair(
            tasks=tasks,
            run_id="t",
            http_get=http_get,
            sleep_func=lambda _s: None,
            sleep_seconds=0,
        )
        self.assertEqual(calls["n"], 2)
        self.assertTrue(out["rate_limited"])
        self.assertEqual(out["rows"][0]["default"]["status"], "ok")
        self.assertEqual(out["rows"][0]["readme"]["status"], "error")
        self.assertEqual(out["rows"][1]["default"]["status"], "cancelled")
        self.assertEqual(out["rows"][1]["readme"]["status"], "cancelled")
        self.assertEqual(out["rows"][1]["default"]["attempted_requests"], 0)

    def test_same_session_overlap_uses_returned_names_only(self):
        def http_get(url, headers):
            if "in%3Areadme" in url or "in:readme" in url:
                return make_items("Keep/Both", "Readme/Only")
            return make_items("Keep/Both", "Default/Only")

        out = pair.run_pair(
            tasks=[task("t1", "alpha", repo="keep/both")],
            run_id="t",
            http_get=http_get,
            sleep_func=lambda _s: None,
            sleep_seconds=0,
            seed_repos_by_task={"t1": {"keep/both"}},
        )
        row = pair.build_pair_rows(out, eval_ids=set())[0]
        self.assertEqual(row["kind"], "seed")
        self.assertEqual([pair.canonical(name) for name in row["both"]], ["keep/both"])
        self.assertEqual(row["only_default"], ["Default/Only"])
        self.assertEqual(row["only_readme"], ["Readme/Only"])
        self.assertEqual(row["target_rank_default"], 1)
        self.assertEqual(row["target_rank_readme"], 1)
        self.assertEqual(row["target_repo"], "keep/both")
        self.assertEqual(row["default_count"], 2)
        self.assertEqual(row["readme_count"], 2)


class TestReport(unittest.TestCase):
    def _doc(self, tasks: list[dict]) -> dict:
        return {
            "run_id": "2026-09-28-readme-pair",
            "materials_commit": "a" * 40,
            "started_at": "2026-09-28T00:00:00Z",
            "finished_at": "2026-09-28T00:01:00Z",
            "github_token_used": False,
            "sleep_seconds": 8.0,
            "attempted_requests": 2,
            "successful_requests": 2,
            "rate_limited": False,
            "tasks": tasks,
        }

    def test_report_stays_undecided_and_unrun(self):
        text = pair.render_report(
            self._doc(
                [
                    {
                        "task_id": "zh2en-eval-02",
                        "direction": "zh2en",
                        "kind": "eval",
                        "query": "q",
                        "default_status": "ok",
                        "readme_status": "ok",
                        "default_error": "",
                        "readme_error": "",
                        "default_count": 0,
                        "readme_count": 1,
                        "both": [],
                        "only_default": [],
                        "only_readme": ["Owner/FromReadme"],
                        "target_repo": None,
                        "target_rank_default": None,
                        "target_rank_readme": None,
                    }
                ]
            )
        )
        self.assertIn("未决定", text)
        self.assertIn("B/C/M 未运行", text)
        self.assertIn("用途判定未运行", text)
        self.assertIn("`Owner/FromReadme`", text)
        self.assertNotIn("包含 awesome", text)
        self.assertNotIn("%", text)

    def test_unknown_fields_are_not_relabeled(self):
        doc = self._doc(
            [
                {
                    "task_id": "en2zh-eval-03",
                    "direction": "en2zh",
                    "kind": "eval",
                    "query": "q",
                    "default_status": "ok",
                    "readme_status": "ok",
                    "default_error": "",
                    "readme_error": "",
                    "default_count": 0,
                    "readme_count": 1,
                    "both": [],
                    "only_default": [],
                    "only_readme": ["vinta/awesome-python"],
                    "target_repo": None,
                    "target_rank_default": None,
                    "target_rank_readme": None,
                }
            ]
        )
        doc["attempted_requests"] = 2
        doc["matched_fields"] = {"default": {}, "readme": {"unknown": 1}}
        doc["shape_check"] = {
            "task_id": "en2zh-eval-03",
            "text_matches_len": 0,
            "top": ["vinta/awesome-python"],
        }
        text = pair.render_report(doc)
        self.assertIn("unknown 1 行", text)
        self.assertIn("text_matches` 长度为 0", text)
        self.assertIn("配对的 2 次之外", text)
        self.assertIn("包含 awesome", text)
        self.assertNotIn("readme 1 行", text)

    def test_failed_side_is_not_compared(self):
        text = pair.render_report(
            self._doc(
                [
                    {
                        "task_id": "seed-zh2en-02",
                        "direction": "zh2en",
                        "kind": "seed",
                        "query": "q",
                        "default_status": "error",
                        "readme_status": "cancelled",
                        "default_error": "HTTP Error 403: rate limit exceeded",
                        "readme_error": "cancelled",
                        "default_count": None,
                        "readme_count": None,
                        "both": [],
                        "only_default": [],
                        "only_readme": [],
                        "target_repo": "sunsations/speed_read",
                        "target_rank_default": None,
                        "target_rank_readme": None,
                    }
                ]
            )
        )
        self.assertIn("未比较", text)
        self.assertIn("HTTP Error 403: rate limit exceeded", text)
        self.assertNotIn("`Owner/FromReadme`", text)


class TestCli(unittest.TestCase):
    def test_without_live_refuses_network(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-id",
                "dry",
                "--out-dir",
                "/tmp/e1-readme-pair-dry",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 5)
        self.assertIn("refusing network", proc.stdout)
        self.assertFalse(Path("/tmp/e1-readme-pair-dry").exists())

    def test_frozen_queries_build_without_network(self):
        queries = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json,sys; from pathlib import Path;"
                        "sys.path.insert(0, 'experiments/E1-cross-language-search/scripts');"
                        "from e1_batch import load_queries;"
                        "from e1_readme_pair import build_readme_variants;"
                        "tasks=load_queries(Path('experiments/E1-cross-language-search/queries.yaml'))['eval.batch_1'];"
                        "print(json.dumps([build_readme_variants(t)[0]['api_query'] for t in tasks], ensure_ascii=False))"
                    ),
                ],
                cwd=str(ROOT),
                text=True,
            )
        )
        self.assertEqual(len(queries), 20)
        self.assertTrue(all(item.endswith(" in:readme") for item in queries))


if __name__ == "__main__":
    unittest.main()
