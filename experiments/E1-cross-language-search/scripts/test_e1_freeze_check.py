"""The recorded E1 freeze status must match reality.

`run-settings.json` carries freeze pointers. A pointer is only honest if the
commit it names actually contains the material it claims to freeze. This test
recomputes that with `e1_freeze_check` and compares against the recorded
`freeze-status.json`, so the record cannot silently drift away from the tree.

If this fails after you edited anything under `prompts/`, `queries.yaml`, the
seed files, or `run-settings.json`, that is the protocol working: decide whether
the change is a re-freeze or an acknowledged post-freeze edit, then refresh with

    python3 scripts/e1_freeze_check.py --write-status ../freeze-status.json
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e1_freeze_check as freeze  # noqa: E402

E1 = Path(__file__).resolve().parents[1]
RECORDED = E1 / "freeze-status.json"


class FreezeCheckerTests(unittest.TestCase):
    def test_checker_flags_material_absent_at_the_pointer(self):
        result = freeze.check()
        self.assertIn("stale", result)
        self.assertEqual(result["stale"], bool(result["absent_at_frozen_commit"]))

    def test_every_recorded_pointer_commit_exists(self):
        result = freeze.check()
        self.assertEqual(result["missing_pointers"], [], "a recorded freeze SHA does not exist")

    def test_materials_all_have_a_pointer(self):
        settings = json.loads(freeze.RUN_SETTINGS.read_text(encoding="utf-8"))
        pointers = set((settings.get("freeze") or {}).keys())
        for rel in freeze.MATERIALS:
            key = freeze.POINTER_FOR.get(rel.split("experiments/E1-cross-language-search/", 1)[-1])
            self.assertIsNotNone(key, f"no pointer mapped for {rel}")
            self.assertIn(key, pointers, f"{rel} maps to unrecorded pointer {key}")


class RecordedStatusTests(unittest.TestCase):
    def test_recorded_status_matches_the_repository(self):
        self.assertTrue(
            RECORDED.exists(),
            "freeze-status.json is missing; run scripts/e1_freeze_check.py --write-status",
        )
        recorded = json.loads(RECORDED.read_text(encoding="utf-8"))
        actual = freeze.check()
        for field in (
            "status",
            "stale",
            "pointers",
            "absent_at_frozen_commit",
            "modified_since_freeze",
            "unreadable_pointers",
        ):
            self.assertEqual(
                recorded.get(field),
                actual.get(field),
                f"freeze-status.json field {field!r} no longer matches the tree. "
                "If you changed frozen material, either re-freeze or refresh the record with "
                "scripts/e1_freeze_check.py --write-status ../freeze-status.json",
            )

    def test_stale_freeze_is_never_reported_as_frozen(self):
        recorded = json.loads(RECORDED.read_text(encoding="utf-8"))
        if recorded["stale"]:
            # A stale freeze must not be described as frozen anywhere in the record.
            self.assertIn(recorded["freeze_status_field"], (None, "", "pointers-recorded-not-yet-run"))
            self.assertFalse(
                recorded.get("frozen_for_run"),
                "a stale freeze must not be marked frozen_for_run",
            )


if __name__ == "__main__":
    unittest.main()
