"""Validate frozen seed-set.jsonl against the protocol section 2 schema.

No network. Stars and README labels in the file are records of an earlier
fetch; this test does not re-contact GitHub and does not treat them as new
measurements.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E1 = ROOT / "experiments" / "E1-cross-language-search"
SEED = E1 / "seed-set.jsonl"
SCHEMA = E1 / "schemas" / "seed-set.schema.json"
REPO_PAT = re.compile(r"^[^/\s]+/[^/\s]+$")
TIME_PAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def load_rows() -> list[dict]:
    rows = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


class TestSeedSet(unittest.TestCase):
    def test_eight_rows_two_sources_and_low_heat(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        required = schema["required"]
        props = schema["properties"]
        rows = load_rows()
        self.assertEqual(len(rows), 8)
        kinds = {row["source_kind"] for row in rows}
        self.assertEqual(kinds, {"hellogithub", "topic_list"})
        self.assertTrue(any(row["low_heat"] for row in rows))
        self.assertTrue(any(row["stars"] < 100 for row in rows))
        dirs = {row["direction"] for row in rows}
        self.assertEqual(dirs, {"zh2en", "en2zh"})
        ids = [row["seed_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        for row in rows:
            for field in required:
                self.assertIn(field, row, field)
            for key in row:
                self.assertIn(key, props, key)
            self.assertRegex(row["repo"], REPO_PAT)
            self.assertGreaterEqual(row["stars"], 0)
            self.assertEqual(row["low_heat"], row["stars"] < 100)
            self.assertIn(row["direction"], props["direction"]["enum"])
            self.assertIn(row["readme_lang"], props["readme_lang"]["enum"])
            self.assertIn(row["query_lang"], props["query_lang"]["enum"])
            self.assertEqual(row["query_origin"], "reverse_engineered_from_source_blurb")
            self.assertRegex(row["frozen_at"], TIME_PAT)
            self.assertRegex(row["discovered_at"], TIME_PAT)
            self.assertNotIn("github_pat_", json.dumps(row))
            self.assertNotIn("ghp_", json.dumps(row))
            slug = row["repo"].split("/", 1)[1]
            self.assertNotIn(slug.lower(), row["query"].lower())
            if row["source_kind"] == "hellogithub":
                self.assertIsInstance(row["hellogithub_issue"], int)
                self.assertGreaterEqual(row["hellogithub_issue"], 1)
            else:
                self.assertNotIn("hellogithub_issue", row)
            if row["direction"] == "zh2en":
                self.assertEqual(row["query_lang"], "zh")
            else:
                self.assertEqual(row["query_lang"], "en")

    def test_schema_no_longer_requires_star_floor(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["stars"]["minimum"], 0)
        self.assertNotIn("hellogithub_issue", schema["required"])
        self.assertIn("第 2 节", schema["description"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
