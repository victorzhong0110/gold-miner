"""Validate extension manifest and shared test file exist."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"


class TestExtensionPackage(unittest.TestCase):
    def test_manifest_mv3(self):
        man = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man["manifest_version"], 3)
        self.assertIn("service_worker", man["background"])
        self.assertTrue(man["content_scripts"])
        self.assertIn("storage", man["permissions"])
        self.assertNotIn("TODO", json.dumps(man))

    def test_no_secrets_in_extension_tree(self):
        import re

        pats = (re.compile(r"sk-[A-Za-z0-9]{16,}"), re.compile(r"ghp_[A-Za-z0-9]{10,}"))
        for path in EXT.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".json", ".html", ".md", ".css"}:
                text = path.read_text(encoding="utf-8")
                for pat in pats:
                    self.assertFalse(pat.search(text), path)

    def test_getting_started_exists(self):
        text = (ROOT / "docs/guides/getting-started.md").read_text(encoding="utf-8")
        self.assertIn("chrome://extensions", text)
        self.assertIn("10", text)


if __name__ == "__main__":
    unittest.main()
