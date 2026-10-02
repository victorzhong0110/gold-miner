"""Fixture harness tests. No network."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
import e1_value_harness as harness  # noqa: E402
import analyze_other_lang_space as analyze  # noqa: E402


class TestHarness(unittest.TestCase):
    def test_fixture_run_dev_abcm(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            manifest = harness.run_fixture_batch("dev", ["A", "B", "C", "M", "D"], out)
            self.assertEqual(manifest["mode"], "fixture")
            self.assertTrue((out / "candidates.jsonl").is_file())
            fails = [
                json.loads(l)
                for l in (out / "failures.jsonl").read_text(encoding="utf-8").splitlines()
                if l
            ]
            d_rows = [f for f in fails if f["arm"] == "D"]
            self.assertTrue(d_rows)
            self.assertTrue(all(f["code"] == "owner_blocked" for f in d_rows))
            ranks = [
                json.loads(l)
                for l in (out / "rank.jsonl").read_text(encoding="utf-8").splitlines()
                if l
            ]
            self.assertTrue(any(r["task_id"] == "zh2en-dev-01" for r in ranks))
            report = analyze.analyze(out / "rank.jsonl", out / "queries.jsonl")
            self.assertTrue(report["not_an_eval_conclusion"])

    def test_live_refused(self):
        code = harness.main(
            ["--mode", "live", "--out", "/tmp/should-not-matter", "--batch", "dev"]
        )
        self.assertEqual(code, 2)

    def test_eval_refused_while_unfrozen(self):
        code = harness.main(
            ["--mode", "fixture", "--batch", "eval.batch_1", "--out", "/tmp/x"]
        )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
