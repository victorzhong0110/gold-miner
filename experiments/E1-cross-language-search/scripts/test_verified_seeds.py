"""Validate verified-seeds.jsonl against the no-floor schema. No network."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

E1 = Path(__file__).resolve().parents[1]
SEEDS = E1 / "verified-seeds.jsonl"
SCHEMA = E1 / "schemas" / "seed-set.schema.json"


class TestVerifiedSeeds(unittest.TestCase):
    def test_eight_rows_and_no_star_floor(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["stars"]["minimum"], 0)
        self.assertNotIn("hellogithub_issue", schema["required"])
        rows = [
            json.loads(l)
            for l in SEEDS.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        self.assertEqual(len(rows), 8)
        dirs = {r["direction"] for r in rows}
        self.assertEqual(dirs, {"zh2en", "en2zh"})
        stars = [r["stars"] for r in rows]
        self.assertTrue(any(s < 50 for s in stars), "must keep low-star seeds")
        self.assertTrue(all(s >= 0 for s in stars))
        sources = {r["source_kind"] for r in rows}
        self.assertGreaterEqual(len(sources), 2)
        required = schema["required"]
        for row in rows:
            for f in required:
                self.assertIn(f, row, f"{row.get('seed_id')} missing {f}")
            self.assertNotIn("TODO", json.dumps(row, ensure_ascii=False))

    def test_eval_ids_do_not_collide_with_seeds(self):
        q = (E1 / "queries.yaml").read_text(encoding="utf-8")
        for line in SEEDS.read_text(encoding="utf-8").splitlines():
            repo = json.loads(line)["repo"]
            self.assertNotIn("eval_frozen_commit:", repo)


if __name__ == "__main__":
    unittest.main()
