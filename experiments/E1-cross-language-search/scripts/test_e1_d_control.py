"""Tests for the E1 group D (strong control) ingest.

The control is recorded by a human; these tests pin the rules that keep it
honest: hallucinated names are counted, an unchecked name is never a hit, and a
task nobody ran stays owner-blocked instead of being invented.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_d_control as d  # noqa: E402


class NormalizeRepoTests(unittest.TestCase):
    def test_accepts_plain_names(self):
        self.assertEqual(d.normalize_repo("owner/repo"), "owner/repo")
        self.assertEqual(d.normalize_repo("  owner/repo  "), "owner/repo")
        self.assertEqual(d.normalize_repo("Owner.Name/repo-name_1"), "Owner.Name/repo-name_1")

    def test_accepts_pasted_urls_and_backticks(self):
        self.assertEqual(d.normalize_repo("https://github.com/owner/repo"), "owner/repo")
        self.assertEqual(d.normalize_repo("https://github.com/owner/repo/"), "owner/repo")
        self.assertEqual(d.normalize_repo("`owner/repo`"), "owner/repo")

    def test_rejects_anything_that_is_not_owner_repo(self):
        for bad in [
            "",
            "not-a-repo",
            "owner/",
            "/repo",
            "a/b/c",
            "owner/re po",
            "javascript:alert(1)",
            "http://evil.test/owner/repo",
            None,
            42,
            {"repo": "owner/repo"},
        ]:
            self.assertEqual(d.normalize_repo(bad), "", repr(bad))


class NormalizeRowTests(unittest.TestCase):
    def test_requires_task_id(self):
        with self.assertRaises(ValueError):
            d.normalize_row({"repos": []}, 1)
        with self.assertRaises(ValueError):
            d.normalize_row({"task_id": "  ", "repos": []}, 1)

    def test_dedupes_case_insensitively_and_keeps_first_spelling(self):
        row = d.normalize_row(
            {
                "task_id": "t1",
                "repos": ["Owner/Repo", "owner/repo", "other/one"],
                "verified": {"owner/repo": True},
            },
            1,
        )
        self.assertEqual(row["repos"], ["Owner/Repo", "other/one"])
        self.assertEqual(row["unverified"], ["other/one"])

    def test_caps_at_ten_and_flags_over_limit(self):
        repos = [f"o{i}/r{i}" for i in range(13)]
        row = d.normalize_row({"task_id": "t1", "repos": repos}, 1)
        self.assertEqual(len(row["repos"]), d.MAX_REPOS)
        self.assertTrue(row["over_limit"])

    def test_keeps_unusable_names_visible_instead_of_hiding_them(self):
        row = d.normalize_row({"task_id": "t1", "repos": ["ok/one", "garbage"]}, 1)
        self.assertEqual(row["repos"], ["ok/one"])
        self.assertEqual(row["rejected_names"], ["garbage"])


class ScoringTests(unittest.TestCase):
    def test_unverified_name_is_never_counted_as_a_hit(self):
        row = d.normalize_row(
            {"task_id": "t1", "repos": ["a/one", "b/two"], "verified": {"a/one": True}},
            1,
        )
        scored = d.score_row(row)
        self.assertEqual(scored["verified_hits"], ["a/one"])
        # b/two was named but never checked, so it cannot be evidence either way.
        self.assertEqual(scored["unverified_names"], ["b/two"])
        # Unchecked is neither a hit nor a hallucination, and the rate waits.
        self.assertEqual(scored["hallucination_count"], 0)
        self.assertEqual(scored["checked_count"], 1)
        self.assertFalse(scored["fully_checked"])
        self.assertEqual(scored["hallucination_rate"], 0.0)

    def test_failed_verification_is_counted_as_a_hallucination(self):
        row = d.normalize_row(
            {"task_id": "t1", "repos": ["a/real", "b/fake"], "verified": {"a/real": True, "b/fake": False}},
            1,
        )
        scored = d.score_row(row)
        self.assertEqual(scored["verified_count"], 1)
        self.assertEqual(scored["hallucinations"], ["b/fake"])
        self.assertEqual(scored["hallucination_rate"], 0.5)

    def test_timebox_is_reported_not_enforced(self):
        row = d.normalize_row({"task_id": "t1", "repos": [], "elapsed_ms": 9_000_000}, 1)
        self.assertFalse(d.score_row(row)["within_timebox"])
        row = d.normalize_row({"task_id": "t2", "repos": [], "elapsed_ms": 1000}, 1)
        self.assertTrue(d.score_row(row)["within_timebox"])
        row = d.normalize_row({"task_id": "t3", "repos": []}, 1)
        self.assertIsNone(d.score_row(row)["within_timebox"])


class ReportTests(unittest.TestCase):
    def test_unrecorded_task_stays_owner_blocked(self):
        rows = [d.normalize_row({"task_id": "t1", "repos": ["a/one"], "verified": {"a/one": True}}, 1)]
        report = d.build_report(rows, ["t1", "t2"], "run-x")
        self.assertEqual(report["status"], "owner-recorded")
        self.assertEqual(report["evidence_kind"], "owner-recorded")
        self.assertEqual([b["task_id"] for b in report["blocked"]], ["t2"])
        self.assertEqual(report["blocked"][0]["status"], "未运行")
        self.assertEqual(report["totals"]["tasks_blocked"], 1)

    def test_totals_aggregate_named_hits_and_hallucinations(self):
        rows = [
            d.normalize_row(
                {"task_id": "t1", "repos": ["a/one", "b/fake"], "verified": {"a/one": True, "b/fake": False}},
                1,
            ),
            d.normalize_row(
                {"task_id": "t2", "repos": ["c/three"], "verified": {"c/three": True}, "elapsed_ms": 1000},
                2,
            ),
        ]
        totals = d.build_report(rows, None, "run-x")["totals"]
        self.assertEqual(totals["repos_named"], 3)
        self.assertEqual(totals["repos_checked"], 3)
        self.assertEqual(totals["repos_unverified"], 0)
        self.assertEqual(totals["verified_hits"], 2)
        self.assertEqual(totals["hallucinations"], 1)
        self.assertEqual(totals["tasks_fully_checked"], 2)
        self.assertAlmostEqual(totals["hallucination_rate"], 1 / 3)

    def test_totals_do_not_invent_a_rate_from_unchecked_names(self):
        rows = [d.normalize_row({"task_id": "t1", "repos": ["a/one", "b/two"]}, 1)]
        totals = d.build_report(rows, None, "run-x")["totals"]
        self.assertEqual(totals["repos_named"], 2)
        self.assertEqual(totals["repos_checked"], 0)
        self.assertEqual(totals["repos_unverified"], 2)
        self.assertIsNone(totals["hallucination_rate"])
        self.assertEqual(totals["tasks_fully_checked"], 0)

    def test_no_rows_is_not_run_not_a_fake_zero(self):
        report = d.build_report([], ["t1"], "run-x")
        self.assertEqual(report["status"], "not-run")
        self.assertIsNone(report["totals"]["hallucination_rate"])
        self.assertEqual(len(report["blocked"]), 1)


class CliTests(unittest.TestCase):
    def test_cli_reports_not_run_for_an_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "d.jsonl"
            src.write_text("", encoding="utf-8")
            self.assertEqual(d.main(["--input", str(src)]), 3)

    def test_cli_rejects_malformed_json_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "d.jsonl"
            src.write_text("{not json}\n", encoding="utf-8")
            self.assertEqual(d.main(["--input", str(src)]), 2)

    def test_cli_round_trip_preserves_hallucinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "d.jsonl"
            src.write_text(
                json.dumps(
                    {
                        "task_id": "t1",
                        "repos": ["a/one", "b/fake"],
                        "verified": {"a/one": True, "b/fake": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(d.main(["--input", str(src), "--run-id", "r1"]), 0)


if __name__ == "__main__":
    unittest.main()
