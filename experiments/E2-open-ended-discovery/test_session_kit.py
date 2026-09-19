"""E2 session kit completeness. No network."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

E2 = Path(__file__).resolve().parent


class TestSessionKit(unittest.TestCase):
    def test_files(self):
        for name in (
            "session-kit.md",
            "human-candidate-sheet.md",
            "logging-table.md",
            "self-check-templates.md",
            "volunteer-invite.md",
            "session-setup.md",
        ):
            text = (E2 / name).read_text(encoding="utf-8")
            self.assertIn("未运行", text)
            self.assertNotIn("TODO", text)

    def test_two_pairs(self):
        kit = (E2 / "session-kit.md").read_text(encoding="utf-8")
        self.assertIn("P1", kit)
        self.assertIn("P2", kit)
        self.assertIn("A 然后 B", kit)
        self.assertIn("B 然后 A", kit)

    def test_schema(self):
        schema = json.loads(
            (E2 / "schemas" / "e2-session.schema.json").read_text(encoding="utf-8")
        )
        self.assertIn("session_id", schema["required"])
        self.assertFalse(schema.get("additionalProperties", True))

    def test_invite_not_sent(self):
        text = (E2 / "volunteer-invite.md").read_text(encoding="utf-8")
        self.assertIn("未发送", text)


if __name__ == "__main__":
    unittest.main()
