import unittest
from pathlib import Path

E3 = Path(__file__).resolve().parent


class TestChecklist(unittest.TestCase):
    def test_codes(self):
        text = (E3 / "off-the-shelf-checklist.md").read_text(encoding="utf-8")
        for code in (
            "term_drift",
            "negation_flip",
            "constraint_softened",
            "code_broken",
            "relation_lost",
            "unrun",
        ):
            self.assertIn(code, text)
        self.assertIn("未运行", text)


if __name__ == "__main__":
    unittest.main()
