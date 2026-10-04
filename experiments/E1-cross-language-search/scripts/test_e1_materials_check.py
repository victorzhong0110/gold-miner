"""Keep materials-status.json honest about the prompt/pipeline rule.

`e1_materials_check.py` reports only what it can verify mechanically: whether a
prompt mentions a qualifier the pipeline rejects, and the line carrying its
prohibition. It deliberately does not read intent out of Chinese prose -- a first
attempt did, and reported C's "本步不要写 in:readme" and M's "不准加…stars:" as
*permissions*. Both are prohibitions. A checker that invents problems is worse
than no checker.

So the intent-level claims live in materials-status.json with a file:line
citation, and these tests re-assert the cited text still says that. If a prompt
is ever corrected, the citation test fails and the record must be updated. That
is the ratchet: the claim can never rot into a false statement about the repo.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

E1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(E1 / "scripts"))

import e1_materials_check as mc  # noqa: E402

RECORDED = E1 / "materials-status.json"


class CoverageCheckTests(unittest.TestCase):
    def test_presence_is_reported_not_intent(self):
        result = mc.check()
        self.assertIn("arms", result)
        for arm, entry in result["arms"].items():
            self.assertIn("mentioned_qualifiers", entry, arm)
            self.assertIn("prohibition_lines", entry, arm)
            # Presence only: line numbers, never an allowed/forbidden verdict.
            for qualifier, line_numbers in entry["mentioned_qualifiers"].items():
                self.assertIsInstance(line_numbers, list, f"{arm}/{qualifier}")
                self.assertTrue(line_numbers)
                for number in line_numbers:
                    self.assertIsInstance(number, int)
                    self.assertGreaterEqual(number, 1)
            # The report itself must not carry a permission claim.
            self.assertNotIn("divergences", result)
            self.assertNotIn("prompt_says", json.dumps(result, ensure_ascii=False))

    def test_blanket_prohibition_covers_unnamed_qualifiers(self):
        entry = mc.check()["arms"]["B"]
        # "不准加任何…等" is a blanket rule, so nothing is left uncovered.
        self.assertTrue(entry["blanket_prohibition"])
        self.assertEqual(entry["never_mentioned"], [])

    def test_each_arm_cites_the_line_carrying_its_prohibition(self):
        result = mc.check()
        for arm in ("B", "C", "M"):
            lines = result["arms"][arm]["prohibition_lines"]
            self.assertTrue(lines, f"{arm} has no prohibition line to cite")
            for record in lines:
                self.assertIsInstance(record["line"], int)
                self.assertTrue(record["text"].strip())

    def test_rule_comes_from_the_pipeline_not_a_copy(self):
        from e1_pipeline import FORBIDDEN_QUERY_SYNTAX
        self.assertEqual(mc.check()["pipeline_rule"], FORBIDDEN_QUERY_SYNTAX.pattern)


class RecordedClaimTests(unittest.TestCase):
    """Every intent-level claim must still be true at its cited line."""

    def setUp(self):
        self.recorded = json.loads(RECORDED.read_text(encoding="utf-8"))

    def _cited_line(self, citation: str) -> str:
        path, _, lineno = citation.rpartition(":")
        target = E1.parents[1] / path
        self.assertTrue(target.exists(), f"cited file missing: {path}")
        lines = target.read_text(encoding="utf-8").splitlines()
        return lines[int(lineno) - 1]

    def test_recorded_divergences_still_exist_at_their_citations(self):
        for claim in self.recorded.get("recorded_divergences", []):
            line = self._cited_line(claim["citation"])
            self.assertIn(
                claim["quote"], line,
                f"{claim['arm']}/{claim['qualifier']}: cited line no longer contains the quote. "
                "Either the prompt was corrected (update this record) or the line moved.",
            )
            self.assertEqual(claim["pipeline_says"], "rejected")
            self.assertEqual(claim["prompt_says"], "allowed")

    def test_recorded_silent_gaps_still_exist_at_their_citations(self):
        for claim in self.recorded.get("recorded_silent_gaps", []):
            line = self._cited_line(claim["citation"])
            self.assertIn(claim["quote"], line, f"{claim['arm']} citation moved")

    def test_recorded_gap_qualifiers_are_really_unmentioned(self):
        for claim in self.recorded.get("recorded_silent_gaps", []):
            arm = claim["arm"]
            mentioned = mc.check()["arms"][arm]["mentioned_qualifiers"]
            for qualifier in claim["qualifiers"]:
                self.assertNotIn(
                    qualifier, mentioned,
                    f"{arm} prompt now mentions {qualifier}; the recorded gap is stale",
                )

    def test_recorded_status_matches_the_recomputed_coverage(self):
        actual = mc.check()
        for field in ("arms_with_uncovered_qualifiers", "all_qualifiers_covered", "pipeline_rule"):
            self.assertEqual(self.recorded.get(field), actual.get(field), field)

    def test_a_stale_freeze_claim_is_never_recorded_as_resolved(self):
        # Divergences are real and the protocol keeps prompts frozen per batch,
        # so the record must not claim the pipeline rule is the only truth.
        if not self.recorded.get("all_qualifiers_covered"):
            self.assertEqual(
                self.recorded["resolution"]["status"], "not-fixed-in-this-batch",
                "an unresolved divergence must not be recorded as fixed",
            )

    def test_batch_1_divergences_were_never_triggered(self):
        # The recorded runs used these prompts and no query hit the rule, so the
        # defect is latent. Claiming otherwise would misstate what happened.
        for claim in self.recorded.get("recorded_divergences", []):
            self.assertEqual(claim["observed_in_batch_1"], "not-triggered")


if __name__ == "__main__":
    unittest.main()
