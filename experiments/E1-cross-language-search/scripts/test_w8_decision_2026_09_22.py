"""W8 2026-09-22 决策报告的约束检查。不访问网络，不读密钥。

运行（仓库根）：
  python3 -m unittest discover -s experiments/E1-cross-language-search/scripts -p "test_w8_decision_2026_09_22.py"
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REPORT = REPO / "docs" / "reports" / "w8-first-round-decision-2026-09-22.md"
DRAFT = REPO / "docs" / "reports" / "w8-first-round-decision-2026-09-17.md"
DRAFT_SHA256 = "f26f249308d69e46c399ca9fda422a1cd17369fd15b9e28f7637d437a9aa2f37"

DECISIONS = ("搜索：未决定", "推荐：未决定", "翻译：未决定")
UNRUN = (
    "W5：未运行",
    "E6 个人模型：未运行",
    "E8 复测：未运行",
    "E9：未运行",
    "D 对照：未运行",
    "使用者是否愿意继续看：未运行",
)


def _block(text, name):
    start = "<!-- w8-%s -->" % name
    end = "<!-- /w8-%s -->" % name
    begin = text.index(start) + len(start)
    finish = text.index(end, begin)
    return text[begin:finish]


class W8DecisionReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = REPORT.read_text(encoding="utf-8")
        cls.decisions = _block(cls.report, "decisions")
        cls.unrun = _block(cls.report, "unrun")

    def test_report_file_exists(self):
        self.assertTrue(REPORT.is_file())
        self.assertGreater(REPORT.stat().st_size, 0)
        self.assertIn("protocol.md", self.report)
        self.assertIn("第 7 节", self.report)

    def test_september_17_draft_bytes_unchanged(self):
        digest = hashlib.sha256(DRAFT.read_bytes()).hexdigest()
        self.assertEqual(digest, DRAFT_SHA256)
        self.assertIn("w8-first-round-decision-2026-09-17.md", self.report)

    def test_three_scopes_are_undecided(self):
        for line in DECISIONS:
            self.assertIn("- %s" % line, self.decisions)
        for scope in ("搜索", "推荐", "翻译"):
            for outcome in ("继续", "缩小", "暂停"):
                self.assertNotIn("%s：%s" % (scope, outcome), self.report)
        self.assertNotIn("已决定", self.report)
        self.assertNotIn("建议", self.report)

    def test_w5_not_written_as_happened(self):
        self.assertIn("- W5：未运行", self.unrun)
        forbidden = (
            r"W5[^。\n]{0,40}(已完成|已发生|已开展|已进行|已经完成)",
            r"短会话(已经|已)(发生|完成|结束)",
            r"参与者[^，。\n]{0,16}(认为|表示|反馈|完成)",
            r"用户原话",
            r"会话耗时",
            r"有价值的新发现：(?!未运行)",
        )
        for pattern in forbidden:
            self.assertIsNone(
                re.search(pattern, self.report),
                pattern,
            )

    def test_unrun_items_have_no_measured_metrics(self):
        for line in UNRUN:
            self.assertIn("- %s" % line, self.unrun)
        self.assertNotRegex(self.report, r"%")
        self.assertNotRegex(self.report, r"命中率\s*[:：为]?\s*\d")
        self.assertNotRegex(self.report, r"准确率\s*[:：为]?\s*\d")
        self.assertNotRegex(self.report, r"H0[^。\n]{0,24}\d")
        self.assertNotRegex(self.report, r"剩余(?:额度|次数)\s*[:：为是]?\s*\d")
        self.assertNotRegex(self.report, r"remaining")
        self.assertNotRegex(self.report, r"x-ratelimit")
        self.assertNotRegex(self.report, r"排名第\s*\d")
        self.assertNotRegex(self.report, r"total_count\s*[:：]\s*\d")
        self.assertNotRegex(self.report, r"个人模型[^。\n]{0,24}\d+\s*(ms|毫秒)")
        self.assertNotRegex(self.report, r"usage_total_tokens[^。\n]{0,12}\d")
        self.assertNotIn("sk-", self.report)
        self.assertNotIn("ghp_", self.report)
        self.assertNotIn("github_pat_", self.report)


if __name__ == "__main__":
    unittest.main()
