import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestE5Scaffold(unittest.TestCase):
    def test_readme(self):
        text = (Path(__file__).resolve().parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("未运行", text)
        self.assertIn("sanitizeExport", text)
        shared = (ROOT / "extension/src/shared.js").read_text(encoding="utf-8")
        self.assertIn("function sanitizeExport", shared)


if __name__ == "__main__":
    unittest.main()
