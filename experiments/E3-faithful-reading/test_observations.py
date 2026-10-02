"""W6 观察记录骨架检查，可直接运行，不访问网络，不调用模型。

依据：experiments/E3-faithful-reading/translation-contrast-2026-09-18.md
第 3 节（观察模板与 JSONL 字段）、AGENTS.md 第 11/14/22 条
（不伪造结果、未运行即标未运行、不写密钥）。

本测试只断言“骨架完整且诚实为空”：8 行、frag 与语言对正确、
判定列全为未运行、未知列全为未知、无译文内容、无密钥模式。
未来真实对照运行时，须另起新日期 JSONL，不得直接改本文件的值。
"""

import json
import re
import unittest
from pathlib import Path

E3 = Path(__file__).resolve().parent
OBS = E3 / "observations-2026-09-21.jsonl"

EXPECTED_LANG = {
    "F-01": "zh→en",
    "F-02": "zh→en",
    "F-03": "zh→en",
    "F-04": "zh→en",
    "F-05": "en→zh",
    "F-06": "en→zh",
    "F-07": "en→zh",
    "F-08": "zh→en",
}
JUDGMENT_FIELDS = (
    "translation_output",
    "polarity_kept",
    "limit_kept",
    "code_intact",
    "discussion_kept",
    "severe_mistranslation",
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
)


def load_rows():
    rows = []
    for line in OBS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


class TestObservationsSkeleton(unittest.TestCase):
    def test_eight_rows_match_fragment_set(self):
        rows = load_rows()
        self.assertEqual(len(rows), 8)
        self.assertEqual({r["frag"] for r in rows}, set(EXPECTED_LANG))

    def test_lang_pair_matches_contrast_doc(self):
        for row in load_rows():
            self.assertEqual(row["lang_pair"], EXPECTED_LANG[row["frag"]])

    def test_judgments_all_not_run(self):
        for row in load_rows():
            for field in JUDGMENT_FIELDS:
                self.assertEqual(
                    row[field], "未运行", f"{row['frag']}.{field} 必须为未运行"
                )
            self.assertEqual(row["tool"], "未运行")

    def test_unknowns_are_unknown(self):
        for row in load_rows():
            self.assertEqual(row["tool_version"], "未知")
            self.assertEqual(row["original_visible"], "未知")

    def test_no_secrets(self):
        text = OBS.read_text(encoding="utf-8")
        for pat in SECRET_PATTERNS:
            self.assertIsNone(pat.search(text), f"疑似密钥模式: {pat.pattern}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
