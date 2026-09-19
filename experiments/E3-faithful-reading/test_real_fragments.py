"""Offline checks for the 2026-09-19 real-project E3 snippets."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

E3 = Path(__file__).resolve().parent
INDEX = E3 / "fragments-real-2026-09-19.md"
SNIP = E3 / "real-snippets"
SMOKE = E3 / "fragments-2026-09-17.md"

IDS = [f"R-{i:02d}" for i in range(1, 11)]
SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
)


class TestRealFragments(unittest.TestCase):
    def test_smoke_set_still_separate(self):
        smoke = SMOKE.read_text(encoding="utf-8")
        real = INDEX.read_text(encoding="utf-8")
        self.assertIn("冒烟", smoke)
        self.assertIn("冒烟集分开", real)
        self.assertIn("未运行", real)

    def test_ten_snippet_files(self):
        for rid in IDS:
            matches = list(SNIP.glob(f"{rid}-*.txt"))
            self.assertEqual(len(matches), 1, rid)
            text = matches[0].read_text(encoding="utf-8").strip()
            self.assertGreater(len(text), 8, rid)
            self.assertNotIn("TODO", text)

    def test_index_points_to_files(self):
        text = INDEX.read_text(encoding="utf-8")
        for path in SNIP.glob("R-*.txt"):
            self.assertIn(path.name, text)

    def test_cn_and_en_present(self):
        blobs = "\n".join(p.read_text(encoding="utf-8") for p in SNIP.glob("R-*.txt"))
        self.assertIn("请勿在生产环境中使用", blobs)
        self.assertIn("Works only with PostgreSQL", blobs)

    def test_no_secrets(self):
        for path in [INDEX, *SNIP.glob("*.txt")]:
            text = path.read_text(encoding="utf-8")
            for pat in SECRET_RES:
                self.assertFalse(pat.search(text), path.name)


if __name__ == "__main__":
    unittest.main()
